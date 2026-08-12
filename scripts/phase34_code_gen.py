#!/usr/bin/env python3
"""Phase 3+4: Code generation, review, and polish — continues from Phase 1&2 debates."""
import json, subprocess, time, os, sys, re
from pathlib import Path
from datetime import datetime, timezone

API_BASE = "https://aigateway.sangfor.com/v1"
MODEL = "deepseek-v4-pro-202606"
OUTPUT = Path("/Users/qi/Desktop/测试文件夹")
API_KEY = os.environ.get("DEEPSEEK_API_KEY","")

TRANSCRIPT = []

def log(agent, msg, kind="message", **meta):
    TRANSCRIPT.append({"agent":agent,"content":msg,"kind":kind,"ts":datetime.now(timezone.utc).isoformat(),**meta})
    print(f"  [{agent}] {msg[:80]}...", flush=True)

def llm(system, user, max_tok=16000):
    body = {"model":MODEL,"messages":[{"role":"system","content":system},{"role":"user","content":user}],"max_tokens":max_tok,"temperature":0.4}
    payload = json.dumps(body, ensure_ascii=False)
    for i in range(5):
        try:
            proc = subprocess.run(["curl","-s","--max-time","300","--noproxy","*",
                "-X","POST",f"{API_BASE}/chat/completions",
                "-H","Content-Type: application/json",
                "-H",f"Authorization: Bearer {API_KEY}",
                "-d",payload], capture_output=True, text=True, timeout=310)
            if proc.returncode != 0:
                err_info = proc.stderr[:300] if proc.stderr else f"stdout: {proc.stdout[:200]}"
                print(f"  ⚠️ curl failed (rc={proc.returncode}): {err_info}", flush=True)
                time.sleep(15); continue
            d = json.loads(proc.stdout)
            if "error" in d:
                err = d.get("error",{})
                err_msg = err if isinstance(err,str) else err.get("message",str(err)[:300])
                print(f"  ⚠️ API error: {err_msg}", flush=True)
                if "429" in str(err) or "rate" in str(err).lower():
                    time.sleep(15*(i+1)); continue
                time.sleep(10); continue
            content = d["choices"][0]["message"]["content"]
            finish = d["choices"][0].get("finish_reason","")
            usage = d.get("usage",{})
            if not content.strip() and finish=="length":
                if max_tok < 32000:
                    max_tok *= 2
                    body["max_tokens"] = max_tok
                    payload = json.dumps(body, ensure_ascii=False)
                    continue
            return content, usage
        except Exception as ex:
            print(f"  ⚠️ Exception: {ex}", flush=True)
            time.sleep(15); continue
    raise RuntimeError("LLM failed after retries")

def write_file(name, content):
    for lang in ["html","css","javascript","js"]:
        s = content.find(f"```{lang}")
        if s!=-1:
            e = content.find("```",s+3+len(lang))
            if e!=-1:
                content = content[content.find("\n",s)+1:e].strip()
                break
    (OUTPUT/name).write_text(content, encoding="utf-8")
    print(f"  📄 {name}: {len(content)} bytes", flush=True)

# Read debate context from previous run
debate_log = ""
try:
    with open("/tmp/debate_team2.log") as f:
        for line in f:
            if line.startswith("  [") and "]" in line[:20]:
                debate_log += line
except: pass

# Condensed architecture decisions from Phase 1&2
ARCH_SUMMARY = """经过6人团队12轮辩论，达成以下共识：
- 三个文件：index.html + style.css + app.js，零依赖
- HTML元素ID已约定：transactionForm, amount, category, note, transactionList, balance, totalIncome, totalExpense, formError, categoryList, emptyHistory
- CSS设计方向：--color-primary #4f67ff, 卡片式布局, Grid响应式
- JS数据模型：{id, amount(fractional), category, note, date(ISO), type}
- 金额以元为单位存储，支持负数表示支出
- localStorage带版本号
- 深色模式通过CSS prefers-color-scheme实现
- 移动端390px起响应式"""

AGENTS = {
"FE": "你是前端开发，擅长HTML/CSS。代码完整，不省略。",
"BE": "你是后端/JS开发，擅长数据逻辑。代码完整，不省略。",
"Design": "你是UI/UX设计师，对视觉极致挑剔。",
"Arch": "你是架构师，审查代码质量。",
"QA": "你是测试工程师，找Bug专家。",
"PM": "你是产品经理，最终验收。",
}

total_tok = 0

# ===== ROUND 13-14: FE writes + Design reviews HTML =====
print("R13: FE writes index.html...", flush=True)
c, u = llm(AGENTS["FE"],
    f"""基于架构约定写index.html。{ARCH_SUMMARY}

HTML必须：语义化HTML5、ARIA标签、所有约定ID、表单含type=number的amount输入、
datalist分类建议、textarea备注。不要写内联script，只引入<script src="app.js">。
用```html包裹完整代码。""", 16000)
write_file("index.html", c); total_tok += u.get("total_tokens",0)

html = (OUTPUT/"index.html").read_text()
print(f"R14: Design reviews HTML ({len(html)}B)...", flush=True)
c, u = llm(AGENTS["Design"],
    f"""审查HTML代码，找出3-5个具体问题。{ARCH_SUMMARY}\n\nHTML前2000字符：{html[:2000]}""", 8000)
log("Design", c[:300], "html_review"); total_tok += u.get("total_tokens",0)

# ===== ROUND 15: FE revises HTML =====
print("R15: FE revises HTML...", flush=True)
c, u = llm(AGENTS["FE"],
    f"""根据审查意见修改HTML。审查：{c[:1000]}\n\n当前HTML：{html[:1500]}\n\n输出完整HTML(```html)""", 16000)
write_file("index.html", c); total_tok += u.get("total_tokens",0)

# ===== ROUND 16-18: FE writes + Design reviews + revises CSS =====
html2 = (OUTPUT/"index.html").read_text()
print("R16: FE writes style.css...", flush=True)
c, u = llm(AGENTS["FE"],
    f"""写style.css。{ARCH_SUMMARY}\n\nHTML结构：{html2[:1500]}\n\n必须：CSS变量、Grid/Flexbox、响应式(390px)、过渡动画、深色模式(prefers-color-scheme)、现代简洁设计。用```css包裹。""", 16000)
write_file("style.css", c); total_tok += u.get("total_tokens",0)

css = (OUTPUT/"style.css").read_text()
print(f"R17: Design reviews CSS ({len(css)}B)...", flush=True)
c, u = llm(AGENTS["Design"],
    f"""审查CSS，挑3-5个视觉问题。CSS前1500字符：{css[:1500]}""", 8000)
log("Design", c[:300], "css_review"); total_tok += u.get("total_tokens",0)

print("R18: FE revises CSS...", flush=True)
c, u = llm(AGENTS["FE"],
    f"""根据审查修改CSS。审查：{c[:1000]}\n\n当前CSS：{css[:1500]}\n\n输出完整CSS(```css)""", 16000)
write_file("style.css", c); total_tok += u.get("total_tokens",0)

# ===== ROUND 19-21: BE writes + Arch reviews + revises JS =====
html_final = (OUTPUT/"index.html").read_text()
print("R19: BE writes app.js...", flush=True)
c, u = llm(AGENTS["BE"],
    f"""写app.js。{ARCH_SUMMARY}\n\nHTML：{html_final[:2000]}\n\n必须：Transaction管理、localStorage(带try/catch)、表单验证、事件委托、统计计算、深色模式检测、数据导出CSV功能。用```javascript包裹。""", 24000)
write_file("app.js", c); total_tok += u.get("total_tokens",0)

js = (OUTPUT/"app.js").read_text()
print(f"R20: Arch reviews JS ({len(js)}B)...", flush=True)
c, u = llm(AGENTS["Arch"],
    f"""审查app.js，指出架构问题。JS前2000字符：{js[:2000]}""", 8000)
log("Arch", c[:300], "js_review"); total_tok += u.get("total_tokens",0)

print("R21: BE revises JS...", flush=True)
c, u = llm(AGENTS["BE"],
    f"""根据审查修改app.js。审查：{c[:1000]}\n\n当前JS：{js[:1500]}\n\n输出完整JS(```javascript)""", 24000)
write_file("app.js", c); total_tok += u.get("total_tokens",0)

# ===== ROUND 22: QA tests =====
html_e = (OUTPUT/"index.html").read_text()
js_e = (OUTPUT/"app.js").read_text()
print("R22: QA testing...", flush=True)
c, u = llm(AGENTS["QA"],
    f"""审查最终代码找Bug。HTML：{html_e[:1500]}\nJS：{js_e[:1500]}\n列出：ID不匹配、逻辑错误、边界遗漏。""", 8000)
log("QA", c[:400], "qa_report"); total_tok += u.get("total_tokens",0)

# ===== ROUND 23-24: Fix QA issues =====
print("R23: FE fixes QA HTML/CSS...", flush=True)
c, u = llm(AGENTS["FE"],
    f"""根据QA报告修复HTML/CSS。QA：{c[:1200]}\nHTML：{html_e[:1500]}\nCSS：{(OUTPUT/'style.css').read_text()[:1500]}\n输出```html和```css""", 24000)
for tag,fn in [("html","index.html"),("css","style.css")]:
    s=c.find(f"```{tag}"); e=c.find("```",s+3+len(tag)) if s!=-1 else -1
    if s!=-1 and e!=-1: (OUTPUT/fn).write_text(c[c.find("\n",s)+1:e].strip())
total_tok += u.get("total_tokens",0)

print("R24: BE fixes QA JS...", flush=True)
c, u = llm(AGENTS["BE"],
    f"""根据QA修复app.js。QA：{c[:1200]}\nJS：{(OUTPUT/'app.js').read_text()[:1500]}\n输出```javascript""", 24000)
write_file("app.js", c); total_tok += u.get("total_tokens",0)

# ===== ROUND 25: PM final acceptance =====
print("R25: PM final acceptance...", flush=True)
c, u = llm(AGENTS["PM"],
    f"""最终验收。文件：index.html({(OUTPUT/'index.html').stat().st_size}B) style.css({(OUTPUT/'style.css').stat().st_size}B) app.js({(OUTPUT/'app.js').stat().st_size}B)\n是否满足需求？""", 8000)
log("PM", c[:400], "final_acceptance"); total_tok += u.get("total_tokens",0)

# ===== SUMMARY =====
print(f"\n🎉 Phase 3+4 完成！总Tokens: {total_tok}")
for f in ["index.html","style.css","app.js"]:
    fp = OUTPUT/f
    print(f"  {'✅' if fp.exists() else '❌'} {f}: {fp.stat().st_size if fp.exists() else 0}B")

with open(OUTPUT/".phase34_transcript.jsonl","w") as f:
    for t in TRANSCRIPT:
        f.write(json.dumps(t,ensure_ascii=False)+"\n")
