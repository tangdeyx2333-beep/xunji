import os
import posixpath
import re
from typing import Any, Dict, Optional

from app.core.config import (
    ALIYUN_OSS_ACCESS_KEY_ID,
    ALIYUN_OSS_ACCESS_KEY_SECRET,
    ALIYUN_OSS_BUCKET,
    ALIYUN_OSS_ENDPOINT,
    ALIYUN_OSS_PREFIX,
    ALIYUN_OSS_REGION,
)

_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename(filename: str) -> str:
    basename = os.path.basename(filename or "attachment")
    sanitized = _FILENAME_SAFE_RE.sub("_", basename).strip("._")
    return sanitized or "attachment"


class AliyunOssService:
    def __init__(self) -> None:
        self._bucket = None
        self._oss = None

    def _get_client(self) -> Any:
        """
        获取阿里云 OSS Client (基于 alibabacloud_oss_v2)
        注意：V2 SDK 不再支持 Bucket 对象，而是直接返回 Client，使用时需在请求参数中指定 bucket 名称。
        """
        # 如果已经初始化过 client，直接返回
        if getattr(self, '_client', None) is not None:
            return self._client

        # 检查必要的环境变量
        if not (
                ALIYUN_OSS_ACCESS_KEY_ID and ALIYUN_OSS_ACCESS_KEY_SECRET and ALIYUN_OSS_ENDPOINT and ALIYUN_OSS_BUCKET):
            raise RuntimeError(
                "Missing required Aliyun OSS envs: ALIYUN_OSS_ACCESS_KEY_ID/ALIYUN_OSS_ACCESS_KEY_SECRET/ALIYUN_OSS_ENDPOINT/ALIYUN_OSS_BUCKET"
            )

        try:
            from alibabacloud_oss_v2.credentials import StaticCredentialsProvider
            import alibabacloud_oss_v2 as oss
        except ImportError as exc:
            raise RuntimeError("阿里 OSS 依赖 alibabacloud_oss_v2 未安装，请安装 requirements.txt") from exc

        # 1. 加载默认配置
        self._oss = oss
        cfg = oss.config.load_default()

        # 2. 配置凭证提供者
        cfg.credentials_provider = StaticCredentialsProvider(
            access_key_id=ALIYUN_OSS_ACCESS_KEY_ID,
            access_key_secret=ALIYUN_OSS_ACCESS_KEY_SECRET
        )

        # 3. 配置 Endpoint
        cfg.endpoint = ALIYUN_OSS_ENDPOINT

        # 4. 配置 Region (如果存在)
        if ALIYUN_OSS_REGION:
            cfg.region = ALIYUN_OSS_REGION

        # 5. 创建 Client
        self._client = oss.Client(cfg)

        return self._client

    def upload_bytes(
            self,
            *,
            user_id: str,
            conversation_id: str,
            message_id: str,
            filename: str,
            content: bytes,
            content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        safe_name = _sanitize_filename(filename)
        # 拼接路径
        key = posixpath.join(ALIYUN_OSS_PREFIX, user_id, conversation_id, message_id, safe_name)

        # 准备请求头
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type

        # 【关键修改】构建 V2 的 PutObjectRequest 对象
        # 必须显式传入 bucket=ALIYUN_OSS_BUCKET
        if self._oss is None:
            self._get_client()
        request = self._oss.PutObjectRequest(
            bucket=ALIYUN_OSS_BUCKET,
            key=key,
            body=content,
            headers=headers or None
        )
        # 使用 client 发送请求对象
        # res 的类型是 PutObjectResult
        print(request.bucket, request.key, request.headers)
        res = self._get_client().put_object(request)

        print("*" * 20)
        print(f"Upload Success. ETag: {res.etag}, RequestId: {res.request_id}")
        return {"key": key, "filename": safe_name, "content_type": content_type or "", "size": len(content)}

    def sign_get_url(self, *, key: str, expires_seconds: int) -> str:
        if self._oss is None:
            self._get_client()
        pre_result = self._get_client().presign(
            self._oss.GetObjectRequest(
                bucket=ALIYUN_OSS_BUCKET,  # 需明确指定存储空间名称
                key=key,
            ),
            expires_in=expires_seconds,  # 过期时间参数名改为expires_in
            slash_safe=True  # slash_safe作为独立参数传递
        )
        return pre_result.url  # 从返回对象中获取URL


aliyun_oss_service = AliyunOssService()
