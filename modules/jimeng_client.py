"""
即梦 API 客户端 — 火山引擎 V4 签名

使用方式：
    client = JimengClient(ak="...", sk="...")
    
    # 检查是否可用
    if client.ready:
        urls = client.generate_image("一只猫在窗台晒太阳")
        
    # 或从配置自动读取
    client = JimengClient.from_config()
    
依赖：requests（标准库 urllib 也可以，但 requests 更方便）
"""

import json
import hashlib
import hmac
import time
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


# ============================================================
# V4 签名
# ============================================================

def _sign_v4(method, url_path, query, body_str, ak, sk):
    """火山引擎 V4 HMAC-SHA256 签名"""
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    body_hash = hashlib.sha256(body_str.encode()).hexdigest()

    canonical_headers = (
        f"content-type:application/json\n"
        f"host:visual.volcengineapi.com\n"
        f"x-date:{amz_date}\n"
    )
    signed_headers = "content-type;host;x-date"

    canonical_request = (
        f"{method}\n{url_path}\n{query}\n"
        f"{canonical_headers}\n{signed_headers}\n{body_hash}"
    )

    credential_scope = f"{date_stamp}/cn-north-1/cv/request"
    string_to_sign = (
        f"HMAC-SHA256\n{amz_date}\n{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
    )

    k_date = hmac.new(sk.encode(), date_stamp.encode(), hashlib.sha256).digest()
    k_region = hmac.new(k_date, b"cn-north-1", hashlib.sha256).digest()
    k_service = hmac.new(k_region, b"cv", hashlib.sha256).digest()
    k_signing = hmac.new(k_service, b"request", hashlib.sha256).digest()
    sig = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

    auth = (
        f"HMAC-SHA256 Credential={ak}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={sig}"
    )

    return {
        "Content-Type": "application/json",
        "X-Date": amz_date,
        "Authorization": auth,
    }


# ============================================================
# 客户端
# ============================================================

_BASE_URL = "https://visual.volcengineapi.com"
_ACTION_SUBMIT = "CVSync2AsyncSubmitTask"
_ACTION_QUERY = "CVSync2AsyncGetResult"
_VERSION = "2022-08-31"


class JimengClient:
    """即梦 API 客户端"""

    # 服务列表
    SERVICES = {
        "t2i_v30": {
            "name": "文生图3.0",
            "req_key": "jimeng_t2i_v30",
            "type": "image",
        },
        "t2i_v31": {
            "name": "文生图3.1",
            "req_key": "jimeng_t2i_v31",
            "type": "image",
        },
        "t2v_v30": {
            "name": "视频3.0 文生视频",
            "req_key": "jimeng_t2v_v30_1080p",
            "type": "video",
        },
    }

    def __init__(self, ak="", sk="", enabled=False):
        self.ak = ak
        self.sk = sk
        self.enabled = enabled

    @property
    def ready(self):
        """是否可用：已启用 + AK/SK 非空"""
        return self.enabled and bool(self.ak) and bool(self.sk)

    @classmethod
    def from_config(cls):
        """从内容工坊 config.yaml 读取配置"""
        try:
            from utils.config_loader import get

            cfg = get("api_keys.jimeng", {})
            return cls(
                ak=cfg.get("ak", ""),
                sk=cfg.get("sk", ""),
                enabled=cfg.get("enabled", False),
            )
        except Exception as e:
            logger.warning(f"[即梦] 读取配置失败: {e}")
            return cls()

    # ---------- 底层调用 ----------

    def _call(self, action, body):
        """发起 V4 签名请求"""
        query = urlencode({"Action": action, "Version": _VERSION})
        url = f"{_BASE_URL}/?{query}"
        body_str = json.dumps(body, ensure_ascii=False)
        headers = _sign_v4("POST", "/", query, body_str, self.ak, self.sk)

        try:
            import requests

            resp = requests.post(
                url, data=body_str, headers=headers, timeout=60
            )
            return resp.json()
        except ImportError:
            # fallback: urllib
            import urllib.request
            import urllib.error

            req = urllib.request.Request(
                url, data=body_str.encode(), headers=headers, method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                return json.loads(e.read())
        except Exception as e:
            logger.error(f"[即梦] 请求失败: {e}")
            return {"error": str(e)}

    def _poll_result(self, req_key, task_id, max_retries=30, interval=2):
        """轮询异步任务结果"""
        for i in range(max_retries):
            time.sleep(interval)
            body = {
                "req_key": req_key,
                "task_id": task_id,
                "req_json": json.dumps({
                    "return_url": True,
                    "logo_info": {"add_logo": False},
                }),
            }
            result = self._call(_ACTION_QUERY, body)
            data = result.get("data") or result.get("result", {})

            # 提取图片 URL
            urls = data.get("image_urls", [])
            if urls:
                return {"urls": urls, "task_id": task_id}

            status = data.get("status", "")
            if status == "failed":
                msg = data.get("error_message", "未知错误")
                return {"error": msg, "task_id": task_id}

        return {"error": "轮询超时", "task_id": task_id}

    # ---------- 公开 API ----------

    def generate_image(self, prompt, service="t2i_v30", size=(1024, 1024)):
        """
        文生图
        
        Args:
            prompt: 图片描述
            service: 服务类型 (t2i_v30 / t2i_v31)
            size: (宽, 高)
        
        Returns:
            {"urls": [...], "task_id": "..."} 或 {"error": "..."}
        """
        if not self.ready:
            return {"error": "即梦未启用或 Key 未配置"}

        svc = self.SERVICES.get(service)
        if not svc or svc["type"] != "image":
            return {"error": f"不支持的服务: {service}"}

        body = {
            "req_key": svc["req_key"],
            "prompt": prompt,
            "width": size[0],
            "height": size[1],
            "seed": -1,
            "req_json": json.dumps({
                "return_url": True,
                "logo_info": {"add_logo": False},
            }),
        }

        logger.info(f"[即梦] 文生图: {prompt[:50]}...")
        result = self._call(_ACTION_SUBMIT, body)

        # 提取 task_id
        task_id = result.get("data", {}).get("task_id", "")
        if not task_id:
            return {"error": result.get("error", "提交失败")}

        return self._poll_result(svc["req_key"], task_id)

    def generate_video(self, prompt, service="t2v_v30", size=(1920, 1080)):
        """
        文生视频
        
        Args:
            prompt: 视频内容描述
            service: 服务类型 (t2v_v30)
            size: 分辨率
        
        Returns:
            {"urls": [...], "task_id": "..."} 或 {"error": "..."}
        """
        if not self.ready:
            return {"error": "即梦未启用或 Key 未配置"}

        svc = self.SERVICES.get(service)
        if not svc or svc["type"] != "video":
            return {"error": f"不支持的服务: {service}"}

        body = {
            "req_key": svc["req_key"],
            "prompt": prompt,
            "seed": -1,
        }

        logger.info(f"[即梦] 文生视频: {prompt[:50]}...")
        result = self._call(_ACTION_SUBMIT, body)

        task_id = result.get("data", {}).get("task_id", "")
        if not task_id:
            return {"error": result.get("error", "提交失败")}

        return self._poll_result(svc["req_key"], task_id)


# ============================================================
# 简易调用（不实例化，直接调）
# ============================================================

def generate_image(prompt, service="t2i_v30"):
    """一行调用：从配置读取并生图"""
    client = JimengClient.from_config()
    return client.generate_image(prompt, service)

def generate_video(prompt, service="t2v_v30"):
    """一行调用：从配置读取并生视频"""
    client = JimengClient.from_config()
    return client.generate_video(prompt, service)
