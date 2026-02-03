import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", os.getenv("KMP_DUPLICATE_LIB_OK", "TRUE"))
