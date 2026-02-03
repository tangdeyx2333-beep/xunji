import os
import posixpath
import re
from typing import Any, Dict, Optional

from qcloud_cos import CosConfig, CosS3Client

from app.core.config import (
    COS_BUCKET,
    COS_PREFIX,
    COS_PUBLIC_BASE_URL,
    COS_REGION,
    COS_SECRET_ID,
    COS_SECRET_KEY,
    COS_UPLOAD_ENABLED,
)


_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_filename(filename: str) -> str:
    basename = os.path.basename(filename or "attachment")
    sanitized = _FILENAME_SAFE_RE.sub("_", basename).strip("._")
    return sanitized or "attachment"


class OssService:
    def __init__(self) -> None:
        self._client: Optional[CosS3Client] = None

    def _get_client(self) -> CosS3Client:
        if self._client is not None:
            return self._client
        if not COS_UPLOAD_ENABLED:
            raise RuntimeError("COS_UPLOAD_ENABLED is false")
        if not (COS_SECRET_ID and COS_SECRET_KEY and COS_REGION and COS_BUCKET):
            raise RuntimeError("Missing required COS envs: COS_SECRET_ID/COS_SECRET_KEY/COS_REGION/COS_BUCKET")
        config = CosConfig(Region=COS_REGION, SecretId=COS_SECRET_ID, SecretKey=COS_SECRET_KEY)
        self._client = CosS3Client(config)
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
        key = posixpath.join(COS_PREFIX, user_id, conversation_id, message_id, safe_name)

        client = self._get_client()
        extra_args: Dict[str, Any] = {}
        if content_type:
            extra_args["ContentType"] = content_type

        client.put_object(Bucket=COS_BUCKET, Body=content, Key=key, **extra_args)

        if COS_PUBLIC_BASE_URL:
            url = f"{COS_PUBLIC_BASE_URL.rstrip('/')}/{key}"
        else:
            url = client.get_object_url(Bucket=COS_BUCKET, Key=key)

        return {"key": key, "url": url, "filename": safe_name, "content_type": content_type or "", "size": len(content)}


oss_service = OssService()

