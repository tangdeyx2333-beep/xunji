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

    def _get_bucket(self) -> Any:
        if self._bucket is not None:
            return self._bucket
        if not (ALIYUN_OSS_ACCESS_KEY_ID and ALIYUN_OSS_ACCESS_KEY_SECRET and ALIYUN_OSS_ENDPOINT and ALIYUN_OSS_BUCKET):
            raise RuntimeError(
                "Missing required Aliyun OSS envs: ALIYUN_OSS_ACCESS_KEY_ID/ALIYUN_OSS_ACCESS_KEY_SECRET/ALIYUN_OSS_ENDPOINT/ALIYUN_OSS_BUCKET"
            )
        try:
            import oss2
        except Exception as exc:
            raise RuntimeError("阿里 OSS 依赖 oss2 未安装，请安装 requirements.txt / requirements-dev.txt") from exc
        auth = oss2.Auth(ALIYUN_OSS_ACCESS_KEY_ID, ALIYUN_OSS_ACCESS_KEY_SECRET)
        if ALIYUN_OSS_REGION:
            self._bucket = oss2.Bucket(auth, ALIYUN_OSS_ENDPOINT, ALIYUN_OSS_BUCKET, region=ALIYUN_OSS_REGION)
        else:
            self._bucket = oss2.Bucket(auth, ALIYUN_OSS_ENDPOINT, ALIYUN_OSS_BUCKET)
        return self._bucket

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
        key = posixpath.join(ALIYUN_OSS_PREFIX, user_id, conversation_id, message_id, safe_name)
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        self._get_bucket().put_object(key, content, headers=headers or None)
        return {"key": key, "filename": safe_name, "content_type": content_type or "", "size": len(content)}

    def sign_get_url(self, *, key: str, expires_seconds: int) -> str:
        return self._get_bucket().sign_url("GET", key, expires_seconds, slash_safe=True)


aliyun_oss_service = AliyunOssService()
