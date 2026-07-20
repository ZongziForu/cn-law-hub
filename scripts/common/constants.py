"""Constants and configuration for cn-law-hub scripts."""

import os
import re

VERIFY_SSL = os.getenv("NPC_LAW_VERIFY_SSL", "0") == "1"
NO_CACHE = os.getenv("NPC_LAW_NO_CACHE", "0") == "1"
MAX_RETRIES = 4

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 cn-law-hub/1.0"
)
BASE_BACKOFF = 1.0
MAX_BACKOFF = 30.0

SAFE_CHAR_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
EM_TAG_RE = re.compile(r"</?em[^>]*>", re.IGNORECASE)
SPACE_RE = re.compile(r"\s+")

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
