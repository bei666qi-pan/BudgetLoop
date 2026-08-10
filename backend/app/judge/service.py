"""Durable judge lifecycle, deterministic gates and structured model verdicts."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.ai_gateway.client import GatewayClient, GatewayError
from app.ai_gateway.config import resolve_gateway_config
from app.api.common import create_run
from app.budget.manager import BudgetRejected, TaskBudgetManager
from app.core.enums import RunStatus, Strategy, TERMINAL_STATUSES
from app.core.models import (
    ExecutionEvent,
    JudgeFinding,
    JudgeGateResult,
    JudgePolicy,
    JudgeRound,
    LlmCall,
    SessionMessage,
    Task,
    TaskRun,
    WorkContainer,
    WorkSession,
    utcnow,
)

JUDGE_ROLE = "汇总裁判"
JUDGE_SESSION_KEY = "system-judge"
DEFAULT_GATES = [
    "required_roles_completed",
    "message_confirmations",
    "evidence_verifiable",
    "workspace_compliant",
    "integration_published",
    "tests_passed",
    "build_passed",
    "target_artifacts_exist",
]
DEFAULT_SAFETY_LIMITS = {"max_rounds": 12, "max_pending_replies": 20}


def _emit(session: Session, container: WorkContainer, judge: WorkSession, event_type: str, payload: dict) -> None:
    session.add(
        ExecutionEvent(
            run_id=judge.current_run_id,
            container_id=container.id,
            type=event_type,
            payload=payload,
        )
    )


def ensure_judge_session(session: Session, container: WorkContainer) -> WorkSession | None:
    """Idempotently provision the mandatory judge for non-terminal teams."""
    if container.lifecycle_state in {"completed", "archived"}:
        return None
    existing = session.execute(
        select(WorkSession).where(
            WorkSession.container_id == container.id,
            WorkSession.session_kind == "judge",
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    task = Task(
        name=f"{container.name} · {JUDGE_ROLE}",
        description=(
            "系统裁判只读取数据库证据、门禁与公开消息；不得修改产品文件。"
            "必须在硬门禁通过后才调用模型评价，并返回严格结构化 verdict。"
        ),
        workdir=container.base_workdir,
        acceptance_criteria="硬门禁失败不得 approve；模型或证据异常必须 blocked。",
        template="locate_issue",
        require_approval=False,
        idempotency_key=f"judge-task:{container.id}",
    )
    session.add(task)
    session.flush()
    run = create_run(
        session,
        task,
        attempt_no=1,
        strategy=Strategy.DYNAMIC,
        budget_fields={
            "max_total_tokens": 60_000,
            "max_llm_calls": 20,
            "max_wall_time_seconds": 3600,
            "max_active_runtime_seconds": 1200,
            "max_cost": 10,
            "max_parallel_llm_calls": 1,
        },
        model_config={
            "execution_engine": "codex",
            "folder_access": "isolated",
            "judge_session": True,
            "agent_step_timeout": 1200,
        },
    )
    judge = WorkSession(
        container_id=container.id,
        role=JUDGE_ROLE,
        goal="汇总证据、执行确定性门禁、定向追问并给出结构化裁决。",
        private_context="系统管理；无产品文件写权限；不得泄露隐藏推理。",
        status=RunStatus.PENDING.value,
        task_id=task.id,
        current_run_id=run.id,
        worktree_enabled=False,
        session_kind="judge",
        system_managed=True,
        idempotency_key=JUDGE_SESSION_KEY,
    )
    session.add(judge)
    session.add(
        JudgePolicy(
            container_id=container.id,
            gates=[{"name": name, "required": True} for name in DEFAULT_GATES],
            model_config={"verdicts": ["approve", "rework", "blocked"], "temperature": 0},
            safety_limits=dict(DEFAULT_SAFETY_LIMITS),
        )
    )
    session.flush()
    _emit(session, container, judge, "judge_state_changed", {"state": "ready", "session_id": str(judge.id)})
    return judge


def backfill_judges(session: Session) -> int:
    containers = list(
        session.execute(
            select(WorkContainer).where(WorkContainer.lifecycle_state.in_(["active", "paused"]))
        ).scalars()
    )
    created = 0
    for container in containers:
        before = len(container.sessions)
        if ensure_judge_session(session, container) is not None and len(container.sessions) == before:
            # relationship may be stale; use durable query below
            pass
    session.flush()
    for container in containers:
        count = session.scalar(
            select(func.count()).select_from(WorkSession).where(
                WorkSession.container_id == container.id,
                WorkSession.session_kind == "judge",
            )
        )
        created += int(count == 1)
    return created


def _gate(name: str, passed: bool, evidence: dict, reason: str | None = None) -> dict:
    return {"gate_name": name, "passed": bool(passed), "evidence": evidence, "failure_reason": reason}


def deterministic_gates(
    container: WorkContainer,
    judge: WorkSession,
    evidence: dict[str, Any],
) -> list[dict]:
    agents_by_id = {str(item.id): item for item in container.sessions if item.id != judge.id}
    applied = (container.preset_snapshot or {}).get("applied_roles") or []
    required_ids = {
        str(item.get("session_id"))
        for item in applied
        if isinstance(item, dict) and item.get("session_id")
    }
    agents = (
        [agents_by_id[item_id] for item_id in required_ids if item_id in agents_by_id]
        if required_ids
        else list(agents_by_id.values())
    )
    completed = [
        item for item in agents
        if item.current_run is not None and item.current_run.status == RunStatus.COMPLETED.value
    ]
    acknowledged = [
        item for item in container.messages if item.delivery_state in {"acknowledged", "delivered"}
    ]
    judge_responses = [
        item for item in container.messages
        if item.recipient_session_id == judge.id and item.sender_session_id is not None
    ]
    refs = evidence.get("evidence_refs") or []
    workspace_ok = all(
        (not item.worktree_enabled) or bool(item.worktree_path)
        for item in agents
    )
    target_paths = [Path(str(path)) for path in evidence.get("target_artifacts") or []]
    artifacts_exist = bool(target_paths) and all(path.exists() for path in target_paths)
    return [
        _gate(
            "required_roles_completed",
            bool(agents) and len(completed) == len(agents),
            {"required": len(agents), "completed": len(completed)},
            None if bool(agents) and len(completed) == len(agents) else "必要角色尚未全部完成",
        ),
        _gate(
            "message_confirmations",
            bool(acknowledged and judge_responses),
            {"acknowledged": len(acknowledged), "judge_responses": len(judge_responses)},
            None if acknowledged and judge_responses else "缺少真实消息确认或裁判回复",
        ),
        _gate("evidence_verifiable", bool(refs), {"refs": refs}, None if refs else "缺少可验证证据引用"),
        _gate("workspace_compliant", workspace_ok, {"sessions": len(agents)}, None if workspace_ok else "存在不合规工作区"),
        _gate("integration_published", evidence.get("integration_published") is True, {"value": evidence.get("integration_published")}, None if evidence.get("integration_published") is True else "集成分支尚未发布"),
        _gate("tests_passed", evidence.get("tests_passed") is True, {"commands": evidence.get("test_commands") or []}, None if evidence.get("tests_passed") is True else "声明测试未通过"),
        _gate("build_passed", evidence.get("build_passed") is True, {"value": evidence.get("build_passed")}, None if evidence.get("build_passed") is True else "构建未通过"),
        _gate("target_artifacts_exist", artifacts_exist, {"paths": [str(path) for path in target_paths]}, None if artifacts_exist else "目标工件不存在"),
    ]


def _parse_model_verdict(content: str, valid_session_ids: set[str]) -> dict:
    try:
        value = json.loads(content)
    except ValueError as exc:
        raise ValueError("invalid_json") from exc
    if not isinstance(value, dict) or value.get("verdict") not in {"approve", "rework", "blocked"}:
        raise ValueError("invalid_verdict")
    findings = value.get("findings")
    if not isinstance(findings, list):
        raise ValueError("invalid_findings")
    normalized = []
    for item in findings:
        if not isinstance(item, dict) or not str(item.get("summary") or "").strip():
            raise ValueError("invalid_finding")
        responsible = item.get("responsible_session_id")
        if responsible is not None and str(responsible) not in valid_session_ids:
            raise ValueError("invalid_responsible_session")
        normalized.append({
            "summary": str(item["summary"])[:2000],
            "severity": str(item.get("severity") or "medium")[:20],
            "responsible_session_id": str(responsible) if responsible else None,
            "evidence_refs": list(item.get("evidence_refs") or [])[:20],
            "feedback": str(item.get("feedback") or "")[:3000] or None,
        })
    return {
        "verdict": value["verdict"],
        "summary": str(value.get("summary") or "")[:4000],
        "findings": normalized,
        "next_step": str(value.get("next_step") or "")[:3000],
    }


def _model_evaluate(session: Session, container: WorkContainer, judge: WorkSession, round_: JudgeRound, gates: list[dict]) -> dict:
    budget = TaskBudgetManager(session, judge.current_run_id)
    estimate = 6000
    budget.reserve(estimate, 0.02)
    reservation_open = True
    config = resolve_gateway_config()
    prompt = {
        "container_id": str(container.id),
        "project_goal": container.project_goal,
        "sessions": [{"id": str(item.id), "role": item.role, "status": item.status} for item in container.sessions if item.id != judge.id],
        "deterministic_gates": gates,
        "evidence_refs": round_.evidence_refs,
    }
    try:
        response = GatewayClient(config).recommend([
            {"role": "system", "content": "你是汇总裁判。只输出一个JSON对象，不得使用代码围栏或输出隐藏推理。顶层必须且只能包含 verdict、summary、findings、next_step；verdict 必须严格为 approve、rework、blocked 三者之一；findings 必须是数组。示例：{\"verdict\":\"approve\",\"summary\":\"全部证据通过\",\"findings\":[],\"next_step\":\"交付\"}。硬门禁均已通过，但仍可因有证据的质量问题rework；finding可指定给出的responsible_session_id。"},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ])
        tokens = max(1, len(response.content) // 4)
        try:
            verdict = _parse_model_verdict(
                response.content,
                {str(item.id) for item in container.sessions},
            )
        except ValueError as exc:
            budget.settle(estimate, 0.02, tokens, 0)
            reservation_open = False
            session.add(LlmCall(
                run_id=judge.current_run_id,
                call_id=f"judge-{round_.id}",
                iteration=round_.sequence,
                phase="evaluation",
                call_kind="judge",
                agent_name=JUDGE_ROLE,
                model=config.recommendation_model,
                provider=config.kind,
                total_tokens=tokens,
                token_source="estimated",
                request_status="invalid",
                output_summary=response.content[:2000],
                decision=f"parse_error:{exc}",
            ))
            raise
        budget.settle(estimate, 0.02, tokens, 0)
        reservation_open = False
        session.add(LlmCall(
            run_id=judge.current_run_id,
            call_id=f"judge-{round_.id}",
            iteration=round_.sequence,
            phase="evaluation",
            call_kind="judge",
            agent_name=JUDGE_ROLE,
            model=config.recommendation_model,
            provider=config.kind,
            total_tokens=tokens,
            token_source="estimated",
            request_status="success",
            input_summary="judge evidence package",
            output_summary=verdict["summary"],
        ))
        return verdict
    except Exception:
        if reservation_open:
            budget.release(estimate, 0.02)
        raise


def _dispatch_feedback(session: Session, container: WorkContainer, judge: WorkSession, round_: JudgeRound, findings: list[dict], fallback_sessions: list[WorkSession]) -> list[str]:
    recipients: dict[str, tuple[WorkSession, list[dict]]] = {}
    by_id = {str(item.id): item for item in container.sessions if item.id != judge.id}
    for finding in findings:
        sid = finding.get("responsible_session_id")
        if sid and sid in by_id:
            recipients.setdefault(sid, (by_id[sid], []))[1].append(finding)
    if not recipients:
        for item in fallback_sessions[:3]:
            recipients[str(item.id)] = (item, findings or [{"summary": "请补充门禁证据", "evidence_refs": [], "feedback": "完成责任范围并回复裁判。"}])
    message_ids: list[str] = []
    for sid, (recipient, items) in recipients.items():
        rework_run_id = _ensure_rework_run(session, recipient)
        activation_run_id = rework_run_id or recipient.current_run_id
        if rework_run_id is not None:
            rework_run = session.get(TaskRun, rework_run_id)
            rework_config = dict(rework_run.model_config or {})
            questions = [
                item.get("feedback") or item.get("summary") for item in items
            ]
            rework_config["run_instruction"] = (
                "This is a Judge-directed rework run. Publicly acknowledge the "
                "Judge request, inspect the cited evidence, make only the changes "
                "allowed by your Session role, run focused verification, commit "
                "the result on your existing Session branch, and send a concise "
                "public evidence reply to the Judge. Required rework: "
                + json.dumps(questions, ensure_ascii=False)
            )
            rework_config["focused_rework"] = True
            rework_run.model_config = rework_config
        content = json.dumps({
            "conclusion": f"裁判第 {round_.sequence} 轮要求定向返工或补证",
            "evidence": [ref for item in items for ref in item.get("evidence_refs") or []],
            "next_step": "确认收件，完成定向事项，并向汇总裁判Session回复证据。",
            "open_questions": [item.get("feedback") or item.get("summary") for item in items],
        }, ensure_ascii=False)
        message = SessionMessage(
            container_id=container.id,
            sender_session_id=judge.id,
            recipient_session_id=recipient.id,
            author_type="session",
            kind="handoff",
            message_type="system_fact",
            content=content,
            delivery_state="queued",
            idempotency_key=f"judge:{round_.id}:{sid}",
            message_metadata={
                "judge_round_id": str(round_.id),
                "required_response": True,
                **({"rework_run_id": str(rework_run_id)} if rework_run_id else {}),
                "activation_run_id": str(activation_run_id),
            },
        )
        session.add(message)
        session.flush()
        message_ids.append(str(message.id))
    round_.feedback_message_ids = message_ids
    round_.pending_session_ids = list(recipients)
    _emit(session, container, judge, "judge_feedback_dispatched", {"round_id": str(round_.id), "message_ids": message_ids, "recipient_session_ids": list(recipients)})
    return message_ids


def _ensure_rework_run(session: Session, recipient: WorkSession) -> uuid.UUID | None:
    """Continue terminal Agent work in a new run without resetting its budget envelope."""
    current = recipient.current_run
    if current is None or current.status not in {status.value for status in TERMINAL_STATUSES}:
        return None
    task = recipient.task
    prior_runs = list(task.runs)
    prior_budgets = [item.budget for item in prior_runs if item.budget is not None]
    source_budget = current.budget
    run = create_run(
        session,
        task,
        attempt_no=max(item.attempt_no for item in prior_runs) + 1,
        strategy=Strategy(current.strategy),
        budget_fields={
            "max_total_tokens": source_budget.max_total_tokens,
            "max_wall_time_seconds": source_budget.max_wall_time_seconds,
            "max_active_runtime_seconds": source_budget.max_active_runtime_seconds,
            "max_llm_calls": source_budget.max_llm_calls,
            "max_cost": float(source_budget.max_cost),
            "max_parallel_llm_calls": source_budget.max_parallel_llm_calls,
        },
        model_config=dict(current.model_config or {}),
    )
    run.budget.used_tokens = max((int(item.used_tokens or 0) for item in prior_budgets), default=0)
    run.budget.used_calls = max((int(item.used_calls or 0) for item in prior_budgets), default=0)
    run.budget.used_cost = max((float(item.used_cost or 0) for item in prior_budgets), default=0.0)
    run.active_runtime_ms = max((int(item.active_runtime_ms or 0) for item in prior_runs), default=0)
    recipient.current_run_id = run.id
    recipient.status = RunStatus.PENDING.value
    recipient.workspace_status = "PENDING"
    recipient.workspace_error = None
    recipient.updated_at = utcnow()
    session.flush()
    return run.id


def _ensure_judge_runtime_window(session: Session, judge: WorkSession) -> None:
    """Roll an expired judge runtime forward without resetting cumulative usage."""
    current = judge.current_run
    if current is None or current.deadline_at is None or current.deadline_at > utcnow():
        return
    task = judge.task
    prior_runs = list(task.runs)
    source = current.budget
    run = create_run(
        session,
        task,
        attempt_no=max(item.attempt_no for item in prior_runs) + 1,
        strategy=Strategy(current.strategy),
        budget_fields={
            "max_total_tokens": source.max_total_tokens,
            "max_wall_time_seconds": source.max_wall_time_seconds,
            "max_active_runtime_seconds": source.max_active_runtime_seconds,
            "max_llm_calls": source.max_llm_calls,
            "max_cost": float(source.max_cost),
            "max_parallel_llm_calls": source.max_parallel_llm_calls,
        },
        model_config=dict(current.model_config or {}),
    )
    prior_budgets = [item.budget for item in prior_runs if item.budget is not None]
    run.budget.used_tokens = max((int(item.used_tokens or 0) for item in prior_budgets), default=0)
    run.budget.used_calls = max((int(item.used_calls or 0) for item in prior_budgets), default=0)
    run.budget.used_cost = max((float(item.used_cost or 0) for item in prior_budgets), default=0.0)
    run.active_runtime_ms = max((int(item.active_runtime_ms or 0) for item in prior_runs), default=0)
    judge.current_run_id = run.id
    judge.status = RunStatus.PENDING.value
    judge.updated_at = utcnow()
    session.flush()


def evaluate_judge_round(
    session: Session,
    container: WorkContainer,
    evidence: dict[str, Any] | None = None,
    *,
    request_key: str | None = None,
) -> JudgeRound:
    evidence = dict(evidence or {})
    if request_key:
        existing = session.execute(
            select(JudgeRound)
            .options(selectinload(JudgeRound.gates), selectinload(JudgeRound.findings))
            .where(
                JudgeRound.container_id == container.id,
                JudgeRound.request_key == request_key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
    judge = ensure_judge_session(session, container)
    if judge is None:
        raise ValueError("terminal_container")
    session.flush()
    _ensure_judge_runtime_window(session, judge)
    # The system judge consumes its durable inbox directly. Marking these
    # replies acknowledged records real database consumption before gating.
    for message in container.messages:
        if message.recipient_session_id == judge.id and message.delivery_state in {"queued", "injected"}:
            message.delivery_state = "acknowledged"
            message.acknowledged_at = utcnow()
    latest_sequence = session.scalar(select(func.max(JudgeRound.sequence)).where(JudgeRound.container_id == container.id)) or 0
    policy = session.execute(select(JudgePolicy).where(JudgePolicy.container_id == container.id)).scalar_one()
    round_limit = int((policy.safety_limits or {}).get("max_rounds", 12))
    if latest_sequence >= round_limit:
        additional_rounds = evidence.get("operator_additional_rounds")
        if isinstance(additional_rounds, int) and 1 <= additional_rounds <= 4:
            policy.safety_limits = {
                **(policy.safety_limits or {}),
                "max_rounds": round_limit + additional_rounds,
            }
        else:
            judge.status = RunStatus.PAUSED.value
            raise BudgetRejected("judge safety round limit reached")
    if not evidence or set(evidence) == {"operator_additional_rounds"}:
        operator_fields = dict(evidence)
        latest = session.execute(
            select(JudgeRound)
            .where(JudgeRound.container_id == container.id)
            .order_by(JudgeRound.sequence.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest is not None:
            evidence = {**dict(latest.evidence_payload or {}), **operator_fields}
    round_ = JudgeRound(
        container_id=container.id,
        judge_session_id=judge.id,
        sequence=latest_sequence + 1,
        request_key=request_key,
        status="gating",
        phase="deterministic_gates",
        evidence_refs=list(evidence.get("evidence_refs") or []),
        evidence_payload=evidence,
    )
    session.add(round_)
    session.flush()
    _emit(session, container, judge, "judge_state_changed", {"round_id": str(round_.id), "state": "executing_gates"})
    gates = deterministic_gates(container, judge, evidence)
    for item in gates:
        session.add(JudgeGateResult(round_id=round_.id, **item))
        _emit(session, container, judge, "judge_gate_completed", {"round_id": str(round_.id), **item})
    failed = [item for item in gates if not item["passed"]]
    agents = [item for item in container.sessions if item.id != judge.id]
    if failed:
        round_.verdict = "rework"
        round_.status = "waiting_replies"
        round_.phase = "feedback"
        round_.summary = "; ".join(item["failure_reason"] or item["gate_name"] for item in failed)
        judge.status = RunStatus.WAITING_APPROVAL.value
        judge.current_run.status = RunStatus.WAITING_APPROVAL.value
        requested_ids = {
            str(item)
            for item in evidence.get("responsible_session_ids") or []
        }
        responsible_agents = [
            item for item in agents if str(item.id) in requested_ids
        ]
        responsible_id = (
            str(responsible_agents[0].id)
            if len(responsible_agents) == 1
            else None
        )
        findings = [{"summary": item["failure_reason"] or item["gate_name"], "severity": "high", "responsible_session_id": responsible_id, "evidence_refs": [item["evidence"], *(evidence.get("evidence_refs") or [])], "feedback": str(evidence.get("rework_instruction") or "补齐该确定性门禁证据。")[:3000]} for item in failed]
        for item in findings:
            session.add(JudgeFinding(round_id=round_.id, **item))
        _dispatch_feedback(
            session,
            container,
            judge,
            round_,
            findings,
            responsible_agents
            or [item for item in agents if item.status != RunStatus.COMPLETED.value]
            or agents,
        )
    else:
        round_.phase = "model_evaluation"
        _emit(session, container, judge, "judge_state_changed", {"round_id": str(round_.id), "state": "model_evaluating"})
        try:
            verdict = _model_evaluate(session, container, judge, round_, gates)
        except (GatewayError, ValueError) as exc:
            round_.verdict = "blocked"
            round_.status = "blocked"
            round_.summary = f"模型评价不可用或输出无效：{getattr(exc, 'code', str(exc))}"
            judge.status = RunStatus.PAUSED.value
            judge.current_run.status = RunStatus.PAUSED.value
        except BudgetRejected as exc:
            round_.verdict = "blocked"
            round_.status = "paused_budget"
            round_.summary = exc.reason
            judge.status = RunStatus.PAUSED.value
            judge.current_run.status = RunStatus.PAUSED.value
        else:
            round_.model_verdict = verdict
            round_.verdict = verdict["verdict"]
            round_.summary = verdict["summary"]
            round_.status = "approved" if verdict["verdict"] == "approve" else ("blocked" if verdict["verdict"] == "blocked" else "waiting_replies")
            for item in verdict["findings"]:
                session.add(JudgeFinding(round_id=round_.id, **item))
            if verdict["verdict"] == "rework":
                _dispatch_feedback(session, container, judge, round_, verdict["findings"], agents)
            elif verdict["verdict"] == "blocked":
                judge.status = RunStatus.PAUSED.value
                judge.current_run.status = RunStatus.PAUSED.value
            else:
                judge.status = RunStatus.COMPLETED.value
                judge.current_run.status = RunStatus.COMPLETED.value
    round_.updated_at = utcnow()
    _emit(session, container, judge, "judge_verdict_recorded", {"round_id": str(round_.id), "verdict": round_.verdict, "summary": round_.summary})
    return round_


def _round_dict(item: JudgeRound) -> dict:
    return {
        "id": str(item.id), "sequence": item.sequence, "status": item.status,
        "phase": item.phase, "verdict": item.verdict, "summary": item.summary,
        "evidence_refs": item.evidence_refs or [], "model_verdict": item.model_verdict,
        "feedback_message_ids": item.feedback_message_ids or [],
        "pending_session_ids": item.pending_session_ids or [],
        "gates": [{"id": str(g.id), "gate_name": g.gate_name, "passed": g.passed, "evidence": g.evidence, "failure_reason": g.failure_reason} for g in item.gates],
        "findings": [{"id": str(f.id), "responsible_session_id": str(f.responsible_session_id) if f.responsible_session_id else None, "severity": f.severity, "summary": f.summary, "evidence_refs": f.evidence_refs or [], "feedback": f.feedback} for f in item.findings],
        "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat(),
    }


def judge_state(session: Session, container: WorkContainer) -> dict:
    judge = ensure_judge_session(session, container)
    if judge is None:
        return {"enabled": False, "reason": "terminal historical team", "rounds": []}
    policy = session.execute(select(JudgePolicy).where(JudgePolicy.container_id == container.id)).scalar_one()
    rounds = list(session.execute(select(JudgeRound).options(selectinload(JudgeRound.gates), selectinload(JudgeRound.findings)).where(JudgeRound.container_id == container.id).order_by(JudgeRound.sequence)).scalars())
    budget = TaskBudgetManager(session, judge.current_run_id).snapshot().to_dict()
    return {
        "enabled": True,
        "session": {"id": str(judge.id), "role": judge.role, "status": judge.status, "system_managed": True, "budget": budget},
        "policy": {"id": str(policy.id), "gates": policy.gates, "model_config": policy.model_config, "safety_limits": policy.safety_limits},
        "state": rounds[-1].status if rounds else "ready",
        "current_round": _round_dict(rounds[-1]) if rounds else None,
        "rounds": [_round_dict(item) for item in rounds],
        "pending_reply_session_ids": rounds[-1].pending_session_ids if rounds else [],
    }
