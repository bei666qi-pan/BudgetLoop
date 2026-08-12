#!/usr/bin/env python3
"""6-Agent 辩论式团队协作 — 打造个人财务仪表盘。

Agent团队（6人）：
- 产品经理(PM)：需求定义、优先级、验收
- 架构师(Arch)：技术选型、数据模型、API设计
- UI/UX设计师(Design)：视觉设计、交互、无障碍
- 前端开发(FE)：HTML/CSS实现
- 后端开发(BE)：JavaScript逻辑、数据层
- 测试工程师(QA)：测试用例、Bug报告、验证

协作模式：辩论式 — 每个提案都会被其他Agent质疑和挑战，
经过多轮反驳→修正→再审查，直到团队达成共识。
"""

import json, subprocess, time, urllib.request, urllib.error, re, sys
from pathlib import Path
from datetime import datetime, timezone

API_BASE = "https://aigateway.sangfor.com/v1"
MODEL = "deepseek-v4-pro-202606"
OUTPUT = Path("/Users/qi/Desktop/测试文件夹")

import os as _os; API_KEY = _os.environ.get("DEEPSEEK_API_KEY","")

TRANSCRIPT = []

def log(agent, msg, kind="message", **meta):
    entry = {"agent": agent, "content": msg, "kind": kind, "ts": datetime.now(timezone.utc).isoformat(), **meta}
    TRANSCRIPT.append(entry)
    print(f"  [{agent}] {msg[:100]}...")

def llm(system, user, max_tok=16000):
    msgs = [{"role":"system","content":system},{"role":"user","content":user}]
    body = {"model":MODEL,"messages":msgs,"max_tokens":max_tok,"temperature":0.4}
    payload = json.dumps(body, ensure_ascii=False)
    for i in range(5):
        try:
            proc = subprocess.run([
                "curl","-s","--max-time","180","--noproxy","*",
                "-X","POST",f"{API_BASE}/chat/completions",
                "-H","Content-Type: application/json",
                "-H",f"Authorization: Bearer {API_KEY}",
                "-d",payload,
            ], capture_output=True, text=True, timeout=200)
            if proc.returncode != 0:
                err_info = proc.stderr[:300] if proc.stderr else f"stdout: {proc.stdout[:200]}"
                print(f"  ⚠️ curl failed (rc={proc.returncode}): {err_info}")
                time.sleep(10)
                continue
            d = json.loads(proc.stdout)
            if "error" in d:
                err = d.get("error",{})
                err_msg = err if isinstance(err,str) else err.get("message",str(err)[:300])
                print(f"  ⚠️ API error: {err_msg}")
                if "429" in str(err) or "rate" in str(err).lower():
                    time.sleep(15*(i+1))
                    continue
                time.sleep(10)
                continue
            content = d["choices"][0]["message"]["content"]
            finish = d["choices"][0].get("finish_reason","")
            usage = d.get("usage",{})
            if not content.strip() and finish=="length":
                if max_tok < 32000:
                    print(f"  ⚠️ empty content (reasoning), retry {max_tok}->{max_tok*2}")
                    max_tok *= 2
                    body["max_tokens"] = max_tok
                    payload = json.dumps(body, ensure_ascii=False)
                    continue
            return content, usage
        except subprocess.TimeoutExpired:
            print(f"  ⚠️ timeout, retry {i+1}/5")
            time.sleep(15)
            continue
        except Exception as ex:
            print(f"  ⚠️ {ex}, retry {i+1}/5")
            time.sleep(10)
            continue
    raise RuntimeError("LLM failed after retries")

def write_file(name, content):
    # Extract code block
    for lang in ["html","css","javascript","js"]:
        s = content.find(f"```{lang}")
        if s!=-1:
            e = content.find("```",s+3+len(lang))
            if e!=-1:
                content = content[content.find("\n",s)+1:e].strip()
                break
    (OUTPUT/name).write_text(content,encoding="utf-8")
    print(f"  📄 {name}: {len(content)} bytes")

# ================================================================
# AGENT PERSONAS (with strong opinions)
# ================================================================
AGENTS = {
"PM": """你是产品经理，经验丰富但要求极高。你的职责：
- 定义清晰的需求和用户故事
- 质疑任何不合理的功能范围
- 坚持"少即是多"原则，但核心体验必须极致
- 当其他Agent提出不合理建议时，你会毫不留情地反驳
- 你对UI/UX设计和功能完整性非常挑剔
- 最终验收时你会挑出所有不符合用户期望的问题
风格：直接、挑剔、以用户价值为唯一标准""",

"Arch": """你是系统架构师，技术功底深厚，但对过度设计零容忍。你的职责：
- 设计数据模型和模块架构
- 评估技术方案的可行性和可维护性
- 当开发提出不合理的实现方案时，你会直接指出问题
- 你会挑战PM的不合理需求，要求澄清技术约束
- 你坚信简单方案优于复杂方案
- 你会审查所有代码的架构质量
风格：理性、严谨、用事实和代码说话""",

"Design": """你是UI/UX设计师，对视觉和交互有极致追求。你的职责：
- 设计用户界面和交互流程
- 审查前端实现是否符合设计标准
- 你会尖锐批评丑陋的UI和不合理的交互
- 你坚持无障碍标准和响应式设计
- 你会与PM争论用户体验优先级
- 你会要求前端反复修改直到视觉完美
风格：追求美感、注重细节、对丑零容忍""",

"FE": """你是前端开发工程师，擅长HTML/CSS，但有自己的技术判断。你的职责：
- 实现UI/UX设计稿
- 当你认为设计不合理时，你会提出技术异议
- 你会质疑设计师提出的不切实际的视觉效果
- 你会与架构师争论前端架构方案
- 你会要求设计师提供明确的交互规范
风格：务实、有主见、不喜欢被设计师指挥""",

"BE": """你是后端/JavaScript开发工程师，精通数据逻辑。你的职责：
- 实现业务逻辑和数据管理
- 你会质疑前端提出的不合理的API需求
- 你会与架构师争论数据模型设计
- 你会要求PM明确边界条件
- 你注重代码健壮性和错误处理
风格：严谨、注重边界、不喜欢模糊需求""",

"QA": """你是测试工程师，找Bug是你的专长。你的职责：
- 设计测试用例
- 执行测试并报告Bug
- 你会毫不留情地指出所有人的疏漏
- 你会质疑PM的验收标准是否充分
- 你会要求开发提供可测试的接口
- 你关注边界条件、异常输入、性能问题
风格：挑剔、详尽、不放过任何问题""",
}

def debate(round_num, phase, speaker, audience, topic, context="", max_tok=12000):
    """One agent speaks, responding to previous debate context."""
    agent = AGENTS[speaker]
    # Truncate context to prevent exceeding model context window
    ctx = context[-4000:] if len(context) > 4000 else context
    prompt = f"""你当前在团队辩论中发言。这是第{round_num}轮，阶段：{phase}。

你之前收到的来自其他成员的消息（仅显示最后部分）：
{ctx}

现在轮到你发言。话题：{topic}

注意：上下文可能很长但只需关注最后几轮讨论即可，不重要的历史可以忽略。

请以"{speaker}（{['产品经理','架构师','UI/UX设计师','前端开发','后端开发','测试工程师'][['PM','Arch','Design','FE','BE','QA'].index(speaker)]}）："开头，
表达你的观点。你可以：
- 同意或反驳之前的观点
- 提出新的想法
- 要求澄清
- 给出具体的技术方案或修改建议
- 如果涉及代码，给出具体代码片段

保持你的角色风格。简短有力，直击要害。不要礼貌性客套。"""
    content, usage = llm(agent, prompt, max_tok)
    log(speaker, content, "debate", round=round_num, phase=phase)
    return content, usage

def code_gen(round_num, agent_key, instruction, context="", max_tok=24000):
    """Generate code with full context of debate."""
    agent = AGENTS[agent_key]
    prompt = f"""你是{['产品经理','架构师','UI/UX设计师','前端开发','后端开发','测试工程师'][['PM','Arch','Design','FE','BE','QA'].index(agent_key)]}。
当前是第{round_num}轮代码产出。

团队之前的讨论摘要：
{context[:2000]}

请根据以下指令产出代码或文档：
{instruction}

要求：
- 如果是代码，用```html/```css/```javascript包裹完整代码
- 不能有占位符或省略号
- 代码必须完整可运行
- 保持你的角色风格"""
    content, usage = llm(agent, prompt, max_tok)
    log(agent_key, content[:300], "code", round=round_num)
    return content, usage

# ================================================================
# MAIN COLLABORATION
# ================================================================
def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    readme = (OUTPUT/"README.md").read_text()
    context = f"项目需求：\n{readme}"
    total_tok = 0

    # ---------- PHASE 1: REQUIREMENTS DEBATE (6 rounds) ----------
    print("\n"+"="*60)
    print("PHASE 1: 需求辩论 — 6个Agent互相挑战需求定义")
    print("="*60)

    # R1: PM proposes requirements
    c, u = debate(1,"需求定义","PM",["All"],"请基于README提出详细需求方案，包括功能列表、用户故事、优先级。记住你要求很高。",context)
    context += f"\n\n[PM]: {c[:1000]}"; total_tok+=u.get("total_tokens",0)

    # R2: Arch challenges PM's requirements from technical perspective
    c, u = debate(2,"需求辩论","Arch",["PM"],"仔细审查PM的需求方案，从技术可行性角度提出质疑。哪些需求技术上不现实？哪些应该简化？哪些缺少技术细节？",context)
    context += f"\n\n[Arch]: {c[:1000]}"; total_tok+=u.get("total_tokens",0)

    # R3: PM responds to Arch's challenges
    c, u = debate(3,"需求辩论","PM",["Arch"],f"架构师质疑了你的需求：{c[:500]}。请回应：哪些你接受调整？哪些你坚持？为什么？给出修订后的需求。",context)
    context += f"\n\n[PM回应]: {c[:1000]}"; total_tok+=u.get("total_tokens",0)

    # R4: Design challenges PM on UX scope
    c, u = debate(4,"需求辩论","Design",["PM"],"审查当前需求，从用户体验角度提出意见。哪些功能会损害用户体验？缺少哪些关键交互？UI复杂度是否合理？",context)
    context += f"\n\n[Design]: {c[:1000]}"; total_tok+=u.get("total_tokens",0)

    # R5: QA challenges completeness
    c, u = debate(5,"需求辩论","QA",["PM","Design"],"审查需求方案和UX意见，从测试角度提出质疑：验收标准是否可测？边界条件是否覆盖？缺少哪些异常场景？",context)
    context += f"\n\n[QA]: {c[:1000]}"; total_tok+=u.get("total_tokens",0)

    # R6: PM finalizes requirements
    c, u = debate(6,"需求敲定","PM",["All"],f"综合所有人的反馈（Arch/Design/QA），给出最终需求文档。必须包含：1)核心功能 2)优先级 3)验收标准 4)明确不做的内容。这是最终版，所有人必须遵守。",context)
    context += f"\n\n[PM最终需求]: {c[:1500]}"; total_tok+=u.get("total_tokens",0)
    print(f"\n  Phase 1 完成 ({total_tok} tokens)")

    # ---------- PHASE 2: DESIGN DEBATE (6 rounds) ----------
    print("\n"+"="*60)
    print("PHASE 2: 设计辩论 — 架构、UI、数据模型互相挑战")
    print("="*60)

    # R7: Arch proposes architecture
    c, u = debate(7,"架构设计","Arch",["All"],"基于最终需求，提出技术架构方案。包括：文件结构、模块划分、数据流、关键数据结构。",context)
    context += f"\n\n[Arch架构]: {c[:1200]}"; total_tok+=u.get("total_tokens",0)

    # R8: BE challenges data model
    c, u = debate(8,"数据模型辩论","BE",["Arch"],f"审查架构师的数据模型：{c[:800]}。作为实际实现者，提出你的质疑：数据结构是否合理？是否遗漏字段？存储方案有问题吗？",context)
    context += f"\n\n[BE质疑]: {c[:1000]}"; total_tok+=u.get("total_tokens",0)

    # R9: Arch responds and revises
    c, u = debate(9,"架构修订","Arch",["BE"],f"后端质疑了你的数据模型：{c[:800]}。回应这些质疑，给出修订后的数据模型和API接口定义（函数签名）。",context)
    context += f"\n\n[Arch修订]: {c[:1200]}"; total_tok+=u.get("total_tokens",0)

    # R10: Design proposes UI layout and style direction
    c, u = debate(10,"UI设计","Design",["FE","PM"],"基于需求，提出UI设计方案。包括：布局结构、配色方案、组件层次、交互流程。要具体，前端需要能据此实现。",context)
    context += f"\n\n[Design方案]: {c[:1200]}"; total_tok+=u.get("total_tokens",0)

    # R11: FE challenges design feasibility
    c, u = debate(11,"设计可行性","FE",["Design"],f"审查设计师的方案：{c[:800]}。从实现角度提出质疑：哪些效果实现成本过高？哪些响应式方案不现实？你建议怎么调整？",context)
    context += f"\n\n[FE质疑]: {c[:1000]}"; total_tok+=u.get("total_tokens",0)

    # R12: Design and FE negotiate, then Design finalizes
    c, u = debate(12,"设计定稿","Design",["FE"],f"前端质疑了你的设计：{c[:800]}。请给出折中方案和最终设计规范。包括：具体CSS变量名、组件类名约定、响应式断点、动画规范。",context)
    context += f"\n\n[Design最终]: {c[:1500]}"; total_tok+=u.get("total_tokens",0)
    print(f"\n  Phase 2 完成 ({total_tok} tokens)")

    # ---------- PHASE 3: IMPLEMENTATION + REVIEW CYCLES (10 rounds) ----------
    print("\n"+"="*60)
    print("PHASE 3: 实现+审查循环 — 产出代码，互相审查，反复修改")
    print("="*60)

    # R13: FE writes HTML (first draft)
    c, u = code_gen(13,"FE",
        f"根据最终设计规范编写index.html。架构约定：{context[-3000:]}\n\n要求：完整HTML5结构，所有ARIA标签，form元素使用约定的ID。用```html包裹。")
    write_file("index.html", c); total_tok+=u.get("total_tokens",0)

    # R14: Design reviews HTML
    # Read actual file for review
    html_v1 = (OUTPUT/"index.html").read_text()
    c, u = debate(14,"HTML审查","Design",["FE"],
        f"审查以下HTML代码。作为设计师，挑剔地指出：语义结构问题、无障碍缺失、与设计规范的偏差。给出具体修改位置。\n\nHTML前2000字符：{html_v1[:2000]}",context)
    context += f"\n\n[Design审查HTML]: {c[:1000]}"; total_tok+=u.get("total_tokens",0)

    # R15: FE revises HTML based on Design's feedback
    c, u = code_gen(15,"FE",
        f"根据设计师的审查意见修改index.html。审查意见：{context.split('[Design审查HTML]:')[-1][:1500]}\n\n当前HTML：{html_v1[:2000]}\n\n输出完整修改后的HTML，用```html包裹。")
    write_file("index.html", c); total_tok+=u.get("total_tokens",0)

    # R16: FE writes CSS
    html_v2 = (OUTPUT/"index.html").read_text()
    c, u = code_gen(16,"FE",
        f"根据设计规范和HTML结构编写style.css。HTML结构：{html_v2[:1500]}\n\n设计规范：{context[-3000:]}\n\n要求：CSS变量、Grid/Flexbox、响应式（390px起）、过渡动画、深色/浅色支持。用```css包裹完整代码。")
    write_file("style.css", c); total_tok+=u.get("total_tokens",0)

    # R17: Design reviews CSS
    css_v1 = (OUTPUT/"style.css").read_text()
    c, u = debate(17,"CSS审查","Design",["FE"],
        f"审查CSS代码。作为设计师，挑剔地指出：颜色不协调、间距不一致、动画不流畅、响应式断点问题。\n\nCSS前2000字符：{css_v1[:2000]}",context)
    context += f"\n\n[Design审查CSS]: {c[:800]}"; total_tok+=u.get("total_tokens",0)

    # R18: FE revises CSS
    c, u = code_gen(18,"FE",
        f"根据设计师的审查意见修改style.css。审查意见：{context.split('[Design审查CSS]:')[-1][:1000]}\n\n当前CSS：{css_v1[:2000]}\n\n输出完整修改后的CSS，用```css包裹。")
    write_file("style.css", c); total_tok+=u.get("total_tokens",0)

    # R19: BE writes app.js
    html_final = (OUTPUT/"index.html").read_text()
    c, u = code_gen(19,"BE",
        f"基于最终HTML和架构约定编写app.js。\n\nHTML结构：{html_final[:3000]}\n\n架构约定：{context[-3000:]}\n\n要求：完整Transaction管理、localStorage、表单验证、事件委托、统计计算、深色模式切换、数据导出(CSV)。用```javascript包裹完整代码。")
    write_file("app.js", c); total_tok+=u.get("total_tokens",0)

    # R20: Arch reviews JS code
    js_v1 = (OUTPUT/"app.js").read_text()
    c, u = debate(20,"代码审查","Arch",["BE"],
        f"审查app.js代码。从架构角度挑剔：模块划分、命名规范、错误处理、性能问题、安全隐患(XSS)。\n\nJS前2000字符：{js_v1[:2000]}",context)
    context += f"\n\n[Arch审查JS]: {c[:1000]}"; total_tok+=u.get("total_tokens",0)

    # R21: BE revises based on Arch's review
    c, u = code_gen(21,"BE",
        f"根据架构师的审查意见修改app.js。审查意见：{context.split('[Arch审查JS]:')[-1][:1200]}\n\n当前JS：{js_v1[:2000]}\n\n输出完整修改后的app.js，用```javascript包裹。")
    write_file("app.js", c); total_tok+=u.get("total_tokens",0)

    # R22: QA runs mental tests and reports bugs
    html_f = (OUTPUT/"index.html").read_text()
    js_f = (OUTPUT/"app.js").read_text()
    css_f = (OUTPUT/"style.css").read_text()
    c, u = debate(22,"QA测试","QA",["FE","BE"],
        f"审查最终代码，模拟测试执行。请找出所有潜在Bug。\n\nHTML关键部分：{html_f[:2000]}\nJS关键部分：{js_f[:2000]}\n\n请列出：1)ID不匹配 2)逻辑错误 3)边界条件遗漏 4)用户体验问题 5)无障碍缺陷。要具体。",context)
    context += f"\n\n[QA报告]: {c[:1500]}"; total_tok+=u.get("total_tokens",0)
    print(f"\n  Phase 3 完成 ({total_tok} tokens)")

    # ---------- PHASE 4: POLISH & FINAL REVIEW (6 rounds) ----------
    print("\n"+"="*60)
    print("PHASE 4: 精修打磨 — 基于QA报告修复，联合审查")
    print("="*60)

    # R23: FE fixes QA issues in HTML/CSS
    c, u = code_gen(23,"FE",
        f"根据QA报告修复HTML和CSS中的问题。QA报告：{context.split('[QA报告]:')[-1][:1500]}\n\n当前HTML：{html_f[:2000]}\n当前CSS：{css_f[:1500]}\n\n输出修复后的完整HTML(```html)和CSS(```css)。")
    # Extract both
    for tag,fn in [("html","index.html"),("css","style.css")]:
        s=c.find(f"```{tag}"); e=c.find("```",s+3+len(tag)) if s!=-1 else -1
        if s!=-1 and e!=-1:
            (OUTPUT/fn).write_text(c[c.find("\n",s)+1:e].strip())
    total_tok+=u.get("total_tokens",0)

    # R24: BE fixes QA issues in JS
    js_now = (OUTPUT/"app.js").read_text()
    c, u = code_gen(24,"BE",
        f"根据QA报告修复app.js中的问题。QA报告：{context.split('[QA报告]:')[-1][:1500]}\n\n当前JS：{js_now[:2000]}\n\n输出完整的修复后app.js，用```javascript包裹。")
    write_file("app.js", c); total_tok+=u.get("total_tokens",0)

    # R25: Design does final visual review
    c, u = debate(25,"最终视觉审查","Design",["FE","BE"],
        f"最终视觉审查。评判：整体视觉是否达到专业水准？配色是否和谐？间距是否一致？动画是否流畅？暗色模式是否完整？还需要改什么？",context)
    context += f"\n\n[Design最终]: {c[:800]}"; total_tok+=u.get("total_tokens",0)

    # R26: FE makes final polish
    c, u = code_gen(26,"FE",
        f"根据设计师的最终审查意见做最后一轮视觉打磨。审查意见：{context.split('[Design最终]:')[-1][:1000]}\n\n输出修改后的HTML(```html)和CSS(```css)。")
    for tag,fn in [("html","index.html"),("css","style.css")]:
        s=c.find(f"```{tag}"); e=c.find("```",s+3+len(tag)) if s!=-1 else -1
        if s!=-1 and e!=-1:
            (OUTPUT/fn).write_text(c[c.find("\n",s)+1:e].strip())
    total_tok+=u.get("total_tokens",0)

    # R27: PM final acceptance
    html_end = (OUTPUT/"index.html").read_text()
    js_end = (OUTPUT/"app.js").read_text()
    css_end = (OUTPUT/"style.css").read_text()
    c, u = debate(27,"最终验收","PM",["All"],
        f"最终验收。评判：是否满足所有需求？用户体验是否达标？是否有遗漏？\n\n产出摘要：index.html({len(html_end)}B) + style.css({len(css_end)}B) + app.js({len(js_end)}B)\nHTML前1000字符：{html_end[:500]}\nJS前500字符：{js_end[:400]}",context)
    context += f"\n\n[PM验收]: {c[:1000]}"; total_tok+=u.get("total_tokens",0)

    # R28: Arch final sign-off
    c, u = debate(28,"架构验收","Arch",["All"],
        f"架构最终验收。代码是否达到可维护标准？是否有技术债务？",context)
    total_tok+=u.get("total_tokens",0)

    # ---------- SUMMARY ----------
    print("\n"+"="*60)
    print(f"🎉 6人团队辩论式协作完成！")
    print(f"   总轮数: 28轮")
    print(f"   总Tokens: {total_tok}")
    print(f"   参与Agent: 产品经理、架构师、UI/UX设计师、前端开发、后端开发、测试工程师")
    for f in ["index.html","style.css","app.js"]:
        fp = OUTPUT/f
        print(f"   {'✅' if fp.exists() else '❌'} {f}: {fp.stat().st_size if fp.exists() else 0} bytes")

    # Save transcript
    with open(OUTPUT/".team_transcript_v2.jsonl","w") as f:
        for t in TRANSCRIPT:
            f.write(json.dumps(t,ensure_ascii=False)+"\n")
    print(f"   协作记录: {OUTPUT/'.team_transcript_v2.jsonl'}")

if __name__=="__main__":
    main()
