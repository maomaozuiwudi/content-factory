#!/usr/bin/env python3
"""豆包批量审查 — 写结果到文件，避免管道缓冲问题"""
import json, os, ssl, urllib.request, urllib.error, time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

KEY = open(os.path.expanduser("~/voice_clone/.doubao_key")).read().strip()
ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
MODEL = "ep-20260619173945-rbl6v"
PROJECT = r"E:\任务\小红书内容工坊"

PROMPT = """你是一个代码审查员。审查以下代码，只标记3类问题：
1. 逻辑漏洞 -- 边界条件遗漏、空指针、死循环、race condition、类型误用
2. 异常处理缺失 -- try-except未覆盖、错误静默吞掉、资源未释放、超时未设
3. 安全/健壮性 -- 硬编码密钥、SQL注入、路径穿越、命令注入、XSS
输出格式（每个问题一行）：
[严重度] 文件名:行号 | 问题描述 | 建议修复
如果没有问题，只输出：✅ 无问题"""

FILES = [
    "main.py",
    "modules/video_composer.py",
    "modules/copy_engine.py",
    "modules/vision_analyzer.py",
    "modules/local_image.py",
    "modules/素材分析.py",
    "modules/search.py",
    "modules/jimeng_client.py",
    "providers/video/clip.py",
    "providers/video/moviepy.py",
    "providers/copy/deepseek.py",
    "providers/image/pillow.py",
    "providers/image/html_screenshot.py",
    "utils/reference_reader.py",
    "utils/config_loader.py",
]

log_path = os.path.join(PROJECT, "_review_progress.txt")
results = {}

for relpath in FILES:
    abspath = os.path.join(PROJECT, relpath)
    code = open(abspath, encoding="utf-8").read()
    lines = code.count("\n")
    
    line = f"[{relpath}] {lines}行 ... "
    with open(log_path, "a", encoding="utf-8") as lf:
        lf.write(line)
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": f"文件名: {relpath}\n\n```\n{code}\n```"},
        ],
        "temperature": 0.1,
        "max_tokens": 2000,
    }
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=120)
        result = json.loads(resp.read())["choices"][0]["message"]["content"]
        issues = [l for l in result.split("\n") if l.strip().startswith("[")]
        results[relpath] = {"issues": issues, "text": result}
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"{len(issues)}个问题\n")
            for iss in issues:
                lf.write(f"  {iss}\n")
    except urllib.error.HTTPError as e:
        results[relpath] = {"error": f"HTTP {e.code}"}
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"HTTP {e.code}: {e.read().decode()[:200]}\n")
    except Exception as e:
        results[relpath] = {"error": str(e)}
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"出错: {e}\n")
    
    time.sleep(2)

# 写最终报告
total = sum(len(v.get("issues", [])) for v in results.values())
summary = f"\n共审查 {len(results)} 个文件，发现 {total} 个问题\n"
with open(log_path, "a", encoding="utf-8") as lf:
    lf.write(summary)

report_path = os.path.join(PROJECT, "_review_report.json")
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

with open(log_path, "a", encoding="utf-8") as lf:
    lf.write(f"\n完整报告: {report_path}\nDONE\n")
