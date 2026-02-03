import os

from dotenv import load_dotenv

load_dotenv(override=True)


OBJECT_STORAGE_PROVIDER = os.getenv("OBJECT_STORAGE_PROVIDER", "disabled").lower()
SIGNED_URL_EXPIRES_SECONDS_DEFAULT = int(os.getenv("SIGNED_URL_EXPIRES_SECONDS_DEFAULT", "600"))
SIGNED_URL_EXPIRES_SECONDS_MAX = int(os.getenv("SIGNED_URL_EXPIRES_SECONDS_MAX", str(7 * 24 * 3600)))

COS_UPLOAD_ENABLED = os.getenv("COS_UPLOAD_ENABLED", "false").lower() == "true"
COS_SECRET_ID = os.getenv("COS_SECRET_ID", "")
COS_SECRET_KEY = os.getenv("COS_SECRET_KEY", "")
COS_REGION = os.getenv("COS_REGION", "")
COS_BUCKET = os.getenv("COS_BUCKET", "")
COS_PREFIX = os.getenv("COS_PREFIX", "chat-attachments")
COS_PUBLIC_BASE_URL = os.getenv("COS_PUBLIC_BASE_URL", "")

ALIYUN_OSS_ACCESS_KEY_ID = os.getenv("ALIYUN_OSS_ACCESS_KEY_ID", "")
ALIYUN_OSS_ACCESS_KEY_SECRET = os.getenv("ALIYUN_OSS_ACCESS_KEY_SECRET", "")
ALIYUN_OSS_ENDPOINT = os.getenv("ALIYUN_OSS_ENDPOINT", "")
ALIYUN_OSS_REGION = os.getenv("ALIYUN_OSS_REGION", "")
ALIYUN_OSS_BUCKET = os.getenv("ALIYUN_OSS_BUCKET", "")
ALIYUN_OSS_PREFIX = os.getenv("ALIYUN_OSS_PREFIX", "chat-attachments")
