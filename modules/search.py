"""
SearXNG 搜索模块
通过 SearXNG 搜索引擎搜索互联网内容
搜索结果自动按分类保存到参考库
"""

import requests
import json
import urllib.parse
from datetime import datetime

from utils.config_loader import get
from utils.reference_reader import save_search_result


class SearXNGSearch:
    """SearXNG 搜索引擎封装"""

    def __init__(self):
        self.base_url = get("api_keys.searxng.base_url", "http://172.27.202.242:8080")
        self._check_available()

    def _check_available(self):
        """检查 SearXNG 是否可用"""
        try:
            resp = requests.get(f"{self.base_url}/", timeout=5)
            if resp.status_code == 200:
                print(f"[🔍 SearXNG] 已连接: {self.base_url}")
                return True
            else:
                print(f"[⚠️ SearXNG] 返回状态码: {resp.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"[⚠️ SearXNG] 连接失败: {e}")
            return False

    def search(self, query, categories=None, language="zh", pageno=1, max_results=5):
        """
        执行搜索

        Args:
            query: 搜索关键词
            categories: 搜索分类列表，如 ["general", "news", "images"]
            language: 语言代码
            pageno: 页码
            max_results: 最大返回结果数

        Returns:
            dict: {
                "query": str,
                "results": [{"title": str, "url": str, "content": str, ...}],
                "total": int,
            }
        """
        params = {
            "q": query,
            "format": "json",
            "language": language,
            "pageno": pageno,
        }

        if categories:
            params["categories"] = ",".join(categories)

        url = f"{self.base_url}/search"

        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            results = data.get("results", [])
            # 截取最大数量
            results = results[:max_results]

            # 精简结果
            cleaned = []
            for r in results:
                cleaned.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                    "engine": r.get("engine", ""),
                })

            output = {
                "query": query,
                "results": cleaned,
                "total": len(cleaned),
            }

            # 自动保存到参考库
            self._save_to_reference(query, cleaned)

            return output

        except requests.exceptions.RequestException as e:
            print(f"[❌ SearXNG] 搜索失败: {e}")
            return {
                "query": query,
                "results": [],
                "total": 0,
                "error": str(e),
            }
        except (ValueError, json.JSONDecodeError) as e:
            print(f"[❌ SearXNG] 搜索返回非JSON: {e}")
            return {
                "query": query,
                "results": [],
                "total": 0,
                "error": f"JSON解析失败: {e}",
            }

    def _save_to_reference(self, query, results):
        """将搜索结果保存到参考库"""
        if not results:
            return

        # 整理结果摘要
        summary_lines = [f"## 搜索结果: {query}"]
        for r in results[:3]:
            summary_lines.append(
                f"- **{r['title']}**: {r['content'][:150]}"
            )
        summary_text = "\n".join(summary_lines)

        try:
            category, msg = save_search_result(query, summary_text)
            print(f"[📚 参考库] 搜索结果已保存到「{category}」")
        except Exception as e:
            print(f"[⚠️ 参考库] 保存失败: {e}")

    def search_multi_queries(self, queries, max_per_query=3):
        """
        多关键词搜索

        Args:
            queries: 关键词列表
            max_per_query: 每个关键词返回最大结果数

        Returns:
            list: [搜索结果...]
        """
        all_results = []
        for q in queries:
            print(f"[🔍 SearXNG] 搜索: {q}")
            result = self.search(q, max_results=max_per_query)
            all_results.append(result)
        return all_results

    def search_topic(self, topic, keywords=None):
        """
        主题搜索 — 围绕一个主题搜索相关资料

        Args:
            topic: 主题名称
            keywords: 相关关键词列表（可选）

        Returns:
            dict: 汇总结果
        """
        if keywords is None:
            keywords = [topic]

        all_results = self.search_multi_queries(keywords)
        return {
            "topic": topic,
            "searches": all_results,
            "total_results": sum(s["total"] for s in all_results),
        }


# 测试
if __name__ == "__main__":
    print("=== SearXNG 搜索测试 ===\n")

    se = SearXNGSearch()

    print("--- 单次搜索 ---")
    result = se.search("效率工具 开源 推荐", max_results=3)
    print(f"查询: {result['query']}")
    print(f"结果数: {result['total']}")
    for i, r in enumerate(result["results"], 1):
        print(f"  {i}. {r['title']}")
        print(f"     {r['content'][:100]}...")

    print("\n--- 主题搜索 ---")
    topic_result = se.search_topic(
        "效率工具推荐",
        keywords=["效率工具 开源", "生产力工具", "打工人必备软件"]
    )
    print(f"主题: {topic_result['topic']}")
    print(f"总结果: {topic_result['total_results']}")

    print("\nOK")
