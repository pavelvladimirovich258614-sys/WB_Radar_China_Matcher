from __future__ import annotations

from matcher.china.alibaba import (
    AlibabaCaptchaError,
    AlibabaImageSearchDriver,
    AlibabaLoginRequiredError,
    AlibabaNoResultsError,
    AlibabaSearchError,
    parse_results_html,
)
from matcher.china.base import ChinaSearchDriver
from matcher.china.s1688 import (
    S1688CaptchaError,
    S1688ImageSearchDriver,
    S1688LoginRequiredError,
    S1688NoResultsError,
    S1688SearchError,
    is_captcha_html,
    is_empty_results_html,
    is_login_required_html,
    normalize_candidate_url,
    parse_results_html as parse_s1688_results_html,
)

__all__ = [
    "ChinaSearchDriver",
    "AlibabaImageSearchDriver",
    "AlibabaSearchError",
    "AlibabaCaptchaError",
    "AlibabaLoginRequiredError",
    "AlibabaNoResultsError",
    "parse_results_html",
    "S1688ImageSearchDriver",
    "S1688SearchError",
    "S1688CaptchaError",
    "S1688LoginRequiredError",
    "S1688NoResultsError",
    "is_captcha_html",
    "is_login_required_html",
    "is_empty_results_html",
    "normalize_candidate_url",
    "parse_s1688_results_html",
]
