"""
Shared utilities for cn-law-hub scripts.

Provides: cache, rate limiting, HTTP client, file I/O, text utilities,
DOCX/article extraction, Chinese numeral conversion, logger, CLI helpers.
"""

# Re-export constants
# Re-export cache
from .cache import CacheManager, get_cache

# Re-export Chinese numeral conversion
from .chinese_numerals import chinese_to_int, int_to_chinese

# Re-export CLI helpers
from .cli_utils import (
    add_common_cli_args,
    add_no_cache_arg,
    add_output_arg,
    add_rate_limit_arg,
)
from .constants import (
    DEFAULT_USER_AGENT,
    MAX_BACKOFF,
    MAX_RETRIES,
    RETRYABLE_STATUS_CODES,
    VERIFY_SSL,
)

# Re-export DOCX / article helpers
from .docx_utils import (
    extract_article_number,
    extract_paragraphs_from_docx,
    is_article_line,
    match_article_query,
    split_into_articles,
)

# Re-export file I/O
from .file_io import (
    read_jsonl,
    render_markdown_report,
    unique_path,
    write_csv,
    write_json,
    write_jsonl,
    write_text,
)

# Re-export logger
from .logger import setup_logger

# Re-export rate limiter & HTTP client
from .ratelimit import (
    RateLimitConfig,
    RateLimitMode,
    SmartRateLimiter,
    http_request,
    init_limiter,
)

# Re-export text utilities + factory
from .text_utils import (
    clean_text,
    create_crawler_headers,
    decode_filename_from_url,
    ensure_dir,
    extract_year,
    format_request_exception,
    redact_url,
    sanitize_filename,
)

# ---------------------------------------------------------------------------
# Backward-compatible aliases (old private names still work)
# ---------------------------------------------------------------------------
_CacheManager = CacheManager
_RateLimitConfig = RateLimitConfig
_RateLimitMode = RateLimitMode
_SmartRateLimiter = SmartRateLimiter
_cache = get_cache()
