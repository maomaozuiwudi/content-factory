"""
小红书内容工坊 — 豆包审查 102 个问题修复
"""
import os, json

PROJECT = r"E:\任务\小红书内容工坊"

# Read the review report
with open(os.path.join(PROJECT, "_review_report.json"), encoding="utf-8") as f:
    report = json.load(f)

print("="*60)
print("小红书内容工坊代码修复需求文档")
print("="*60)
print()

# Group by severity
files_by_severity = {}
for relpath, data in report.items():
    if "error" in data:
        continue
    issues = data.get("issues", [])
    if not issues:
        continue
    high = [i for i in issues if "[高]" in i or "[严重]" in i or "[高" in i]
    medium = [i for i in issues if "[中]" in i or "[中" in i]
    low = [i for i in issues if "[低]" in i or "[低" in i]
    logic = [i for i in issues if "逻辑" in i and i not in high+medium+low]
    files_by_severity[relpath] = {"high": high, "medium": medium, "low": low + logic}

# Print organized by priority
print("### 🔴 高优先级问题（7个）")
print()
for relpath, sevs in files_by_severity.items():
    for h in sevs["high"]:
        print(f"  **{relpath}**: {h}")
print()

print("### 🟡 中优先级问题")
print()
for relpath, sevs in files_by_severity.items():
    for m in sevs["medium"]:
        print(f"  **{relpath}**: {m}")
print()

print("### 🟢 低优先级（冗余代码/跨平台/测试代码）")
print()
for relpath, sevs in files_by_severity.items():
    for l in sevs["low"]:
        print(f"  **{relpath}**: {l}")
print()

# Count
total = sum(len(v["high"]) + len(v["medium"]) + len(v["low"]) for v in files_by_severity.values())
print(f"总计: {total} 个问题")
