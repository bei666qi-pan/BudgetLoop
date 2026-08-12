#!/usr/bin/env python3
"""Multi-Agent Team Collaboration — 真实多轮沟通产出预算追踪器SPA.

3个Agent角色通过AI Gateway进行多轮协作：
- 技术主管：架构设计、审查、协调
- 前端开发：HTML + CSS
- 后端开发：app.js

每轮都有真实的LLM调用，Agent之间通过团队频道消息沟通。
所有产出写入 /Users/qi/Desktop/测试文件夹/。
"""

import json
import os
import subprocess
import sys
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
import urllib.error

# --- Config ---
API_BASE = "https://aigateway.sangfor.com/v1"
MODEL = "deepseek-v4-pro-202606"
OUTPUT_DIR = Path("/Users/qi/Desktop/测试文件夹")
TRANSCRIPT_FILE = OUTPUT_DIR / ".team_transcript.jsonl"

def get_api_key():
    result = subprocess.run(
        ["security", "find-generic-password", "-s", "DEEPSEEK_API_KEY", "-w"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"❌ 无法读取 API Key: {result.stderr}")
        sys.exit(1)
    return result.stdout.strip()

API_KEY = get_api_key()

# --- Agent Personas ---
AGENTS = {
    "tech_lead": {
        "name": "技术主管",
        "role": "tech_lead",
        "system_prompt": """你是软件开发团队的技术主管。你的职责是：
1. 分析需求文档，设计项目架构
2. 在团队频道发布架构方案和开发计划
3. 审查前端和后端的代码产出
4. 给出具体、可操作的修改意见
5. 最终验收并发布完成声明

规则：
- 回复必须简短精炼，直接给出可执行指令
- 审查时指出具体问题（文件名、行级问题、如何修改）
- 只在达到真实里程碑时发布[PROGRESS]声明
- 不要重复已确认的内容
- 不要猜测或编造未观察到的信息""",
    },
    "frontend": {
        "name": "前端开发",
        "role": "frontend",
        "system_prompt": """你是资深前端开发工程师。你的职责是：
1. 创建 index.html（语义化HTML5、无障碍ARIA标签、表单验证）
2. 创建 style.css（CSS变量、Flexbox/Grid、响应式、过渡动画、现代设计）
3. 先提出HTML元素ID方案，等后端确认后再编码
4. 收到审查意见后认真修改
5. 通过团队频道与后端沟通元素ID约定

规则：
- 在编码前先列出所有HTML元素ID
- 等待后端确认ID无冲突后再写代码
- 所有代码必须完整，不能有占位符
- 使用现代CSS特性：CSS变量、Grid、Flexbox、过渡动画
- 支持移动端响应式（390px起）""",
    },
    "backend": {
        "name": "后端开发",
        "role": "backend",
        "system_prompt": """你是资深JavaScript开发工程师。你的职责是：
1. 创建 app.js（完整的前端逻辑）
2. 实现：Transaction管理、表单验证、CRUD操作、localStorage持久化、余额计算
3. 审查前端提出的HTML元素ID，确认或提出修改
4. 收到审查意见后认真修改
5. 确保与前端HTML完全兼容

规则：
- 先审查前端ID方案，确认后再编码
- 使用现代ES6+语法
- 必须有完整的错误处理
- localStorage读写需要try/catch
- 事件委托优于单独绑定
- 所有代码必须完整，不能有占位符""",
    },
}


def call_llm(agent_key: str, user_message: str, context: str = "") -> str:
    """Call the AI Gateway with the agent's persona."""
    agent = AGENTS[agent_key]
    messages = [{"role": "system", "content": agent["system_prompt"]}]
    if context:
        messages.append({"role": "user", "content": f"当前上下文：\n{context}"})
    messages.append({"role": "user", "content": user_message})

    body = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 8000,
        "temperature": 0.3,
    }

    req = urllib.request.Request(
        f"{API_BASE}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
    )

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return content, usage
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()[:500]
            if e.code == 429:
                wait = 5 * (attempt + 1)
                print(f"  ⚠️ 429 限流，等待 {wait}s...")
                time.sleep(wait)
                continue
            print(f"  ❌ HTTP {e.code}: {err_body}")
            raise
        except Exception as e:
            if attempt < 2:
                time.sleep(3)
                continue
            raise

    raise RuntimeError("LLM call failed after 3 attempts")


def log_transcript(entry: dict):
    """Append to the team transcript."""
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(TRANSCRIPT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def write_file(filename: str, content: str):
    """Write a file to the output directory, extracting code blocks if present."""
    # Extract code block if wrapped in markdown
    if "```" in content:
        lines = content.split("\n")
        code_lines = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            elif line.startswith("```") and in_block:
                in_block = False
                continue
            elif in_block:
                code_lines.append(line)
        if code_lines:
            content = "\n".join(code_lines)

    filepath = OUTPUT_DIR / filename
    filepath.write_text(content, encoding="utf-8")
    print(f"  📄 写入: {filepath} ({len(content)} bytes)")
    return filepath


def main():
    print("=" * 60)
    print("🤖 Agent Team 协作启动")
    print(f"   团队: 技术主管 + 前端开发 + 后端开发")
    print(f"   目标: 预算追踪器 SPA")
    print(f"   输出: {OUTPUT_DIR}")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Read requirements
    readme = (OUTPUT_DIR / "README.md").read_text(encoding="utf-8")
    total_tokens = 0

    # ============================================================
    # ROUND 1: Tech Lead publishes architecture plan
    # ============================================================
    print("\n📋 第1轮：技术主管发布架构方案")
    content, usage = call_llm(
        "tech_lead",
        f"""请分析以下需求文档，发布项目架构方案。方案应包含：
1. HTML结构约定（主要区块，语义元素）
2. CSS类命名规范（BEM或其他约定）
3. 建议的HTML元素ID列表（供前后端约定使用）
4. JS API接口约定（函数签名、数据结构）
5. 开发阶段计划

需求文档：
{readme}

请用简明的结构化格式回复，直接发布到团队频道。""",
    )
    total_tokens += usage.get("total_tokens", 0)
    log_transcript({"round": 1, "agent": "tech_lead", "type": "architecture_plan", "content": content})
    print(f"  ✅ 技术主管发布了架构方案 ({usage.get('total_tokens', 0)} tokens)")
    architecture_plan = content

    # ============================================================
    # ROUND 2: Frontend proposes HTML element IDs
    # ============================================================
    print("\n📋 第2轮：前端开发提出HTML元素ID方案")
    content, usage = call_llm(
        "frontend",
        f"""技术主管发布了以下架构方案，请仔细阅读。

{architecture_plan}

现在请你：
1. 确认收到架构方案
2. 提出你计划使用的所有HTML元素ID列表（每个元素的id属性）
3. 说明每个ID的用途
4. 请后端开发确认这些ID是否满足app.js的DOM操作需求

注意：这只是ID提案，不要写完整的HTML/CSS代码，等后端确认后再编码。""",
    )
    total_tokens += usage.get("total_tokens", 0)
    log_transcript({"round": 2, "agent": "frontend", "type": "id_proposal", "content": content})
    print(f"  ✅ 前端开发提出了ID方案 ({usage.get('total_tokens', 0)} tokens)")
    frontend_id_proposal = content

    # ============================================================
    # ROUND 3: Backend reviews IDs and confirms/requests changes
    # ============================================================
    print("\n📋 第3轮：后端开发审查ID方案")
    content, usage = call_llm(
        "backend",
        f"""前端开发提出了以下HTML元素ID方案，请你仔细审查。

{frontend_id_proposal}

请逐一检查每个ID：
1. 是否满足app.js中DOM操作的需求
2. 是否需要额外的data属性
3. 是否有遗漏的关键元素
4. 给出明确的确认或修改要求

请直接回复前端开发，确认哪些ID可用，哪些需要调整。""",
    )
    total_tokens += usage.get("total_tokens", 0)
    log_transcript({"round": 3, "agent": "backend", "type": "id_review", "content": content})
    print(f"  ✅ 后端开发完成了ID审查 ({usage.get('total_tokens', 0)} tokens)")
    backend_review = content

    # ============================================================
    # ROUND 4: Frontend confirms and writes HTML + CSS
    # ============================================================
    print("\n📋 第4轮：前端开发编写HTML+CSS")
    content, usage = call_llm(
        "frontend",
        f"""后端开发已审查你的ID方案并给出以下反馈：

{backend_review}

现在请：
1. 确认后端的修改意见
2. 根据确认后的ID方案，编写完整的 index.html
3. 编写完整的 style.css

要求：
- index.html：语义化HTML5，表单验证属性，ARIA无障碍标签
- style.css：CSS变量、Flexbox/Grid布局、响应式设计（390px起）、过渡动画
- 现代简洁的UI风格
- 所有文件必须完整，不能有省略号或占位符
- 请在回复中分别用 ```html 和 ```css 代码块包裹两个文件的完整代码""",
    )
    total_tokens += usage.get("total_tokens", 0)
    log_transcript({"round": 4, "agent": "frontend", "type": "code_delivery", "content": content[:500]})
    # Extract and write files
    # Find HTML block
    html_start = content.find("```html")
    html_end = content.find("```", html_start + 7) if html_start != -1 else -1
    css_start = content.find("```css")
    css_end = content.find("```", css_start + 6) if css_start != -1 else -1

    if html_start != -1 and html_end != -1:
        html_code = content[html_start + 7:html_end].strip()
        write_file("index.html", html_code)
    else:
        write_file("index.html", content)

    if css_start != -1 and css_end != -1:
        css_code = content[css_start + 6:css_end].strip()
        write_file("style.css", css_code)

    print(f"  ✅ 前端开发完成了HTML+CSS ({usage.get('total_tokens', 0)} tokens)")

    # ============================================================
    # ROUND 5: Tech Lead reviews frontend code
    # ============================================================
    print("\n📋 第5轮：技术主管审查前端代码")
    # Read the actual files for review
    try:
        html_content = (OUTPUT_DIR / "index.html").read_text(encoding="utf-8")
        css_content = (OUTPUT_DIR / "style.css").read_text(encoding="utf-8")
    except FileNotFoundError:
        html_content = "（文件未找到）"
        css_content = "（文件未找到）"

    content, usage = call_llm(
        "tech_lead",
        f"""前端开发已完成代码。请审查以下文件。

=== index.html ===
{html_content[:3000]}

=== style.css ===
{css_content[:3000]}

请给出具体的审查意见：
1. HTML语义化是否合理
2. 无障碍（ARIA）是否完整
3. CSS布局和响应式是否合理
4. 有哪些需要改进的地方（具体指出）
5. 如果通过，给出明确确认

请直接@前端开发，给出你的审查结论。""",
    )
    total_tokens += usage.get("total_tokens", 0)
    log_transcript({"round": 5, "agent": "tech_lead", "type": "frontend_review", "content": content})
    print(f"  ✅ 技术主管审查了前端代码 ({usage.get('total_tokens', 0)} tokens)")
    frontend_review = content

    # ============================================================
    # ROUND 6: Frontend iterates based on review
    # ============================================================
    print("\n📋 第6轮：前端开发根据审查意见修改")
    content, usage = call_llm(
        "frontend",
        f"""技术主管审查了你的代码，给出以下意见：

{frontend_review}

当前 index.html：
{html_content[:2000]}

当前 style.css：
{css_content[:2000]}

请根据审查意见修改代码，并在回复中提供修改后的完整 index.html 和 style.css。
用 ```html 和 ```css 代码块分别包裹。""",
    )
    total_tokens += usage.get("total_tokens", 0)
    log_transcript({"round": 6, "agent": "frontend", "type": "code_revision", "content": content[:500]})

    html_start = content.find("```html")
    html_end = content.find("```", html_start + 7) if html_start != -1 else -1
    css_start = content.find("```css")
    css_end = content.find("```", css_start + 6) if css_start != -1 else -1

    if html_start != -1 and html_end != -1:
        write_file("index.html", content[html_start + 7:html_end].strip())
    if css_start != -1 and css_end != -1:
        write_file("style.css", content[css_start + 6:css_end].strip())

    print(f"  ✅ 前端开发完成修改 ({usage.get('total_tokens', 0)} tokens)")

    # Reload HTML for backend reference
    html_content = (OUTPUT_DIR / "index.html").read_text(encoding="utf-8")

    # ============================================================
    # ROUND 7: Backend writes app.js
    # ============================================================
    print("\n📋 第7轮：后端开发编写app.js")
    content, usage = call_llm(
        "backend",
        f"""现在前端HTML已最终确定，请基于以下HTML编写完整的app.js。

=== 最终 index.html（关键元素） ===
{html_content[:4000]}

需求：
1. Transaction类/构造函数（id, amount, category, date, note, type）
2. addTransaction() - 含完整表单验证
3. deleteTransaction(id) - 含确认
4. calculateBalance() - 自动计算
5. updateUI() - 更新DOM
6. localStorage读写 - 含try/catch
7. 事件委托
8. 初始化加载
9. 统计：总收入、总支出、余额

用 ```javascript 代码块包裹完整代码。""",
    )
    total_tokens += usage.get("total_tokens", 0)
    log_transcript({"round": 7, "agent": "backend", "type": "code_delivery", "content": content[:500]})

    js_start = content.find("```javascript")
    if js_start == -1:
        js_start = content.find("```js")
    js_end = content.find("```", js_start + 3) if js_start != -1 else -1

    if js_start != -1 and js_end != -1:
        js_code = content[content.find("\n", js_start) + 1:js_end].strip()
    else:
        js_code = content

    write_file("app.js", js_code)
    print(f"  ✅ 后端开发完成了app.js ({usage.get('total_tokens', 0)} tokens)")

    # ============================================================
    # ROUND 8: Tech Lead reviews backend code
    # ============================================================
    print("\n📋 第8轮：技术主管审查后端代码")
    js_content = (OUTPUT_DIR / "app.js").read_text(encoding="utf-8")

    content, usage = call_llm(
        "tech_lead",
        f"""后端开发完成了app.js，请审查。

=== app.js ===
{js_content[:4000]}

请审查：
1. 代码结构是否清晰
2. 错误处理是否完整
3. localStorage读写是否有try/catch
4. 事件委托是否正确
5. 与前端HTML的集成是否匹配
6. 是否有安全问题（XSS等）

请@后端开发给出具体审查意见。""",
    )
    total_tokens += usage.get("total_tokens", 0)
    log_transcript({"round": 8, "agent": "tech_lead", "type": "backend_review", "content": content})
    print(f"  ✅ 技术主管审查了后端代码 ({usage.get('total_tokens', 0)} tokens)")
    backend_review_final = content

    # ============================================================
    # ROUND 9: Backend iterates based on review
    # ============================================================
    print("\n📋 第9轮：后端开发根据审查意见修改")
    content, usage = call_llm(
        "backend",
        f"""技术主管审查了你的app.js，给出以下意见：

{backend_review_final}

当前 app.js：
{js_content[:2000]}

请根据审查意见修改代码，在回复中提供修改后的完整app.js。
用 ```javascript 代码块包裹。""",
    )
    total_tokens += usage.get("total_tokens", 0)
    log_transcript({"round": 9, "agent": "backend", "type": "code_revision", "content": content[:500]})

    js_start = content.find("```javascript")
    if js_start == -1:
        js_start = content.find("```js")
    js_end = content.find("```", js_start + 3) if js_start != -1 else -1

    if js_start != -1 and js_end != -1:
        write_file("app.js", content[content.find("\n", js_start) + 1:js_end].strip())

    print(f"  ✅ 后端开发完成修改 ({usage.get('total_tokens', 0)} tokens)")

    # ============================================================
    # ROUND 10: Final integration review by Tech Lead
    # ============================================================
    print("\n📋 第10轮：技术主管最终验收")
    html_final = (OUTPUT_DIR / "index.html").read_text(encoding="utf-8")
    css_final = (OUTPUT_DIR / "style.css").read_text(encoding="utf-8")
    js_final = (OUTPUT_DIR / "app.js").read_text(encoding="utf-8")

    content, usage = call_llm(
        "tech_lead",
        f"""所有代码已完成最终修改。请进行最终验收。

=== index.html (前500字符) ===
{html_final[:500]}
...（完整文件已写入磁盘）

=== style.css (前500字符) ===
{css_final[:500]}
...（完整文件已写入磁盘）

=== app.js (前500字符) ===
{js_final[:500]}
...（完整文件已写入磁盘）

验收清单：
1. index.html是否可以直接在浏览器打开
2. 表单元素是否与app.js中的ID匹配
3. CSS是否包含响应式设计
4. JS是否包含完整的CRUD和localStorage
5. 三个文件是否构成完整可用的SPA

请发布最终[PROGRESS]声明和验收结论。""",
    )
    total_tokens += usage.get("total_tokens", 0)
    log_transcript({"round": 10, "agent": "tech_lead", "type": "final_review", "content": content})
    print(f"  ✅ 技术主管完成最终验收 ({usage.get('total_tokens', 0)} tokens)")

    # ============================================================
    # Summary
    # ============================================================
    print("\n" + "=" * 60)
    print("🎉 Agent Team 协作完成！")
    print(f"   总轮数: 10轮")
    print(f"   总Tokens: {total_tokens}")
    print(f"   产出文件:")
    for f in ["index.html", "style.css", "app.js"]:
        fp = OUTPUT_DIR / f
        if fp.exists():
            print(f"   ✅ {f}: {fp.stat().st_size} bytes")
        else:
            print(f"   ❌ {f}: 未找到")
    print(f"   协作记录: {TRANSCRIPT_FILE}")
    print("=" * 60)

    # Write summary
    summary = {
        "project": "预算追踪器 SPA",
        "team": ["技术主管", "前端开发", "后端开发"],
        "total_rounds": 10,
        "total_tokens": total_tokens,
        "files": {
            "index.html": (OUTPUT_DIR / "index.html").stat().st_size if (OUTPUT_DIR / "index.html").exists() else 0,
            "style.css": (OUTPUT_DIR / "style.css").stat().st_size if (OUTPUT_DIR / "style.css").exists() else 0,
            "app.js": (OUTPUT_DIR / "app.js").stat().st_size if (OUTPUT_DIR / "app.js").exists() else 0,
        },
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(OUTPUT_DIR / ".team_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary


if __name__ == "__main__":
    main()
