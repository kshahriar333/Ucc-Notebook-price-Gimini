import re
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class LaptopSpecs:
    raw_name: str
    normalized_name: str
    sku: Optional[str] = None
    series: Optional[str] = None
    cpu_brand: Optional[str] = None
    cpu_model: Optional[str] = None
    ram_gb: Optional[int] = None
    ssd_gb: Optional[int] = None
    gpu: Optional[str] = None
    extra_tokens: List[str] = field(default_factory=list)


SKU_PATTERNS = [
    r"\b(?:NX|NH|UN)\.[A-Z0-9]{5}\.[A-Z0-9]{3}\b",
    r"\b(?:A[1357]|AS\d{2}|AL\d{2}|ANV?|SF[G357X]?|PHN?|PT[3579]?|TMP?|TMB?|EX[2]?|CB[357]?|SP[135]?)\d{0,3}-\d{2,3}[A-Z]?-[A-Z0-9]{2,5}\b",
    r"\b(?:A[1357]|AS\d{2}|AL\d{2}|ANV?|SF[G357X]?|PHN?|PT[3579]?|TMP?|TMB?|EX[2]?|CB[357]?|SP[135]?)\d{0,3}-\d{2,3}[A-Z]?\b",
]

SERIES_KEYWORDS = [
    "predator helios neo",
    "predator helios",
    "predator triton",
    "nitro v",
    "nitro 5",
    "nitro 16",
    "nitro",
    "swift go",
    "swift x",
    "swift 3",
    "swift 5",
    "swift",
    "aspire lite",
    "aspire vero",
    "aspire 3",
    "aspire 5",
    "aspire 7",
    "aspire 15",
    "aspire",
    "extensa",
    "travelmate",
    "chromebook",
    "spin",
]


def extract_sku(text: str) -> Optional[str]:
    upper_text = text.upper()
    for pattern in SKU_PATTERNS:
        match = re.search(pattern, upper_text)
        if match:
            return match.group(0)
    return None


def extract_series(text: str) -> Optional[str]:
    lower_text = text.lower()
    for s in SERIES_KEYWORDS:
        if re.search(r"\b" + re.escape(s) + r"\b", lower_text):
            return s.title()
    return None


def extract_cpu(text: str) -> tuple[Optional[str], Optional[str]]:
    t = text.lower()

    # Intel Core Ultra (e.g., Ultra 7 155H, Ultra 5 125H)
    ultra_match = re.search(r"ultra\s*([579])\s*(\d{3}[a-z]{1,2})?", t)
    if ultra_match:
        tier = ultra_match.group(1)
        code = ultra_match.group(2) or ""
        return ("Intel", f"ULTRA-{tier}-{code}".strip("-").upper())

    # Intel Core i3/i5/i7/i9 & Core 3/5/7 (e.g., i5-1334U, Core 3 100U, Core 5 120U)
    intel_match = re.search(
        r"(?:core\s*)?(i[3579]|core\s*[357])\s*[-\s]?\s*(\d{3,5}[a-z]{0,2})\b", t
    )
    if intel_match:
        tier = intel_match.group(1).replace(" ", "")
        code = intel_match.group(2).upper()
        return ("Intel", f"{tier}-{code}")

    # Fallback Intel tier without exact model number
    intel_tier_only = re.search(r"\b(i[3579])\b", t)
    gen_match = re.search(r"\b(1[0-4])(?:th|nd|rd|st)\s*gen\b", t)
    if intel_tier_only:
        gen_str = f"{gen_match.group(1)}th" if gen_match else ""
        return ("Intel", f"{intel_tier_only.group(1)}-{gen_str}".strip("-"))

    # Intel N-series / Celeron (e.g., N100, N200, N4500)
    n_series = re.search(r"\b(?:celeron\s*)?(n\d{3,4})\b", t)
    if n_series:
        return ("Intel", n_series.group(1).upper())

    # AMD Ryzen (e.g., Ryzen 5 7430U, Ryzen 3 7330U
