#!/usr/bin/env python3
"""Fix the HTML-JS element ID mismatch discovered during integration testing."""
import json
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path

API_BASE = "https://aigateway.sangfor.com/v1"
MODEL = "deepseek-v4-pro-202606"
OUTPUT_DIR = Path("/Users/qi/Desktop/测试文件夹")

result = subprocess.run(
    ["security", "find-generic-password", "-s", "DEEPSEEK_API_KEY", "-w"],
    capture_output=True, text=True
)
API_KEY = result.stdout.strip()


def call_llm(system_prompt, user_message):
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    body = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 6000,
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        f"{API_BASE}/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                d = json.loads(r.read())
                return d["choices"][0]["message"]["content"], d.get("usage", {})
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            raise
    raise RuntimeError("LLM call failed")


if __name__ == "__main__":
    html = (OUTPUT_DIR / "index.html").read_text()
    js = (OUTPUT_DIR / "app.js").read_text()

    # Extract HTML IDs
    import re
    html_ids = set(re.findall(r'id="([^"]*)"', html))
    js_ids = set(re.findall(r"getElementById\('([^']*)'\)", js))
    missing = js_ids - html_ids
    extra = html_ids - js_ids

    print(f"HTML IDs: {sorted(html_ids)}")
    print(f"JS IDs: {sorted(js_ids)}")
    print(f"JS expects but HTML missing: {sorted(missing)}")
    print(f"HTML has but JS unused: {sorted(extra)}")

    if not missing:
        print("✅ 所有ID已匹配，无需修复！")
        exit(0)

    # Fix: modify HTML to match JS IDs
    print(f"\n🔧 修复不匹配的ID: {sorted(missing)}")

    # Smart replacement: find similar IDs and replace
    replacements = {}
    for m in missing:
        # Try to find matching near-miss in HTML
        for hid in html_ids:
            if m in hid or hid in m:
                replacements[hid] = m
                print(f"  {hid} -> {m}")
                break

    # Apply replacements
    fixed_html = html
    for old_id, new_id in replacements.items():
        fixed_html = fixed_html.replace(f'id="{old_id}"', f'id="{new_id}"')
        # Also fix for attributes
        fixed_html = fixed_html.replace(f'for="{old_id}"', f'for="{new_id}"')

    (OUTPUT_DIR / "index.html").write_text(fixed_html)
    print(f"\n✅ index.html 已修复 ({len(fixed_html)} bytes)")

    # Verify
    html2 = (OUTPUT_DIR / "index.html").read_text()
    html_ids2 = set(re.findall(r'id="([^"]*)"', html2))
    remaining = js_ids - html_ids2
    if remaining:
        print(f"⚠️ 仍有不匹配: {remaining}")
    else:
        print("✅ 所有ID现已完全匹配！")
