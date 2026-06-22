"""批量豆包审查小红书内容工坊代码"""
import json, os, sys, ssl, urllib.request, urllib.error, time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

DOUBAO_KEY_FILE = os.path.expanduser("~/voice_clone/.doubao_key")
ARK_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
DOUBAO_MODEL = "ep-20260619173945-rbl6v"

PROJECT = r"E:\任务\小红书内容工坊"

CORE_FILES = [
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

REVIEW_PROMPT = """你是一个代码审查员。审查以下代码，只标记3类问题：

1. 逻辑漏洞 -- 边界条件遗漏、空指针、死循环、race condition、类型误用
2. 异常处理缺失 -- try-except未覆盖、错误静默吞掉、资源未释放、超时未设
3. 安全/健壮性 -- 硬编码密钥、SQL注入、路径穿越、命令注入、XSS

输出格式（每个问题一行）：
[严重度] 文件名:行号 | 问题描述 | 建议修复

如果没有问题，只输出：✅ 无问题

不要输出无关信息。不要提风格、命名、性能、注释等问题。"""

def call_doubao(code_text, filename):
    if not os.path.exists(DOUBAO_KEY_FILE):
        return None, "Doubao key not found"
    with open(DOUBAO_KEY_FILE) as f:
        key = f.read().strip()
    payload = {
        "model": DOUBAO_MODEL,
        "messages": [
            {"role": "system", "content": REVIEW_PROMPT},
            {"role": "user", "content": f"文件名: {filename}\n\n```\n{code_text}\n```"},
        ],
        "temperature": 0.1,
        "max_tokens": 2000,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    req = urllib.request.Request(ARK_ENDPOINT, data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=120)
        return json.loads(resp.read())["choices"][0]["message"]["content"], "Doubao"
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        return None, f"HTTP {e.code}: {body}"
    except Exception as e:
        return None, str(e)

def main():
    results = {}
    for relpath in CORE_FILES:
        abspath = os.path.join(PROJECT, relpath)
        if not os.path.exists(abspath):
            results[relpath] = {"error": "文件不存在"}
            continue
        with open(abspath, encoding="utf-8") as f:
            code = f.read()
        lines = code.count("\n")
        print(f"[{relpath}] {lines}行 ... ", end="", flush=True)
        
        result, provider = call_doubao(code, relpath)
        if result is None:
            print(f"跳过 ({provider})")
            results[relpath] = {"error": provider}
        else:
            issues = [l for l in result.split("\n") if l.strip().startswith("[")]
            print(f"{len(issues)}个问题 (via {provider})")
            results[relpath] = {"issues": issues, "text": result}
        
        # 避免频率限制
        time.sleep(1.5)
    
    # 输出汇总
    print("\n" + "=" * 60)
    print("小红书内容工坊 豆包审查汇总")
    print("=" * 60)
    total_issues = 0
    for relpath, data in results.items():
        if "error" in data:
            print(f"\n⚠️  {relpath} — 审查跳过: {data['error']}")
            continue
        issues = data["issues"]
        if not issues:
            print(f"\n✅ {relpath} — 无问题")
        else:
            total_issues += len(issues)
            print(f"\n📋 {relpath} — {len(issues)}个问题:")
            for issue in issues:
                print(f"  {issue}")
    
    print(f"\n{'=' * 60}")
    print(f"共审查 {len(results)} 个文件，发现 {total_issues} 个问题")
    
    # 存报告
    report_path = os.path.join(PROJECT, "_review_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"完整报告: {report_path}")

if __name__ == "__main__":
    main()
