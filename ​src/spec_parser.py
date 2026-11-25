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

    ultra_match = re.search(r"ultra\s*([579])\s*(\d{3}[a-z]{1,2})?", t)
    if ultra_match:
        tier = ultra_match.group(1)
        code = ultra_match.group(2) or ""
        return ("Intel", f"ULTRA-{tier}-{code}".strip("-").upper())

    intel_match = re.search(
        r"(?:core\s*)?(i[3579]|core\s*[357])\s*[-\s]?\s*(\d{3,5}[a-z]{0,2})\b", t
    )
    if intel_match:
        tier = intel_match.group(1).replace(" ", "")
        code = intel_match.group(2).upper()
        return ("Intel", f"{tier}-{code}")

    intel_tier_only = re.search(r"\b(i[3579])\b", t)
    gen_match = re.search(r"\b(1[0-4])(?:th|nd|rd|st)\s*gen\b", t)
    if intel_tier_only:
        gen_str = f"{gen_match.group(1)}th" if gen_match else ""
        return ("Intel", f"{intel_tier_only.group(1)}-{gen_str}".strip("-"))

    n_series = re.search(r"\b(?:celeron\s*)?(n\d{3,4})\b", t)
    if n_series:
        return ("Intel", n_series.group(1).upper())

    ryzen_match = re.search(
        r"(?:ryzen|r)\s*([3579])\s*[-\s]?\s*(\d{4}[a-z]{0,2})\b", t
    )
    if ryzen_match:
        tier = ryzen_match.group(1)
        code = ryzen_match.group(2).upper()
        return ("AMD", f"R{tier}-{code}")

    ryzen_tier_only = re.search(r"\bryzen\s*([3579])\b", t)
    if ryzen_tier_only:
        return ("AMD", f"R{ryzen_tier_only.group(1)}")

    return (None, None)


def extract_ram_gb(text: str) -> Optional[int]:
    t = text.lower()
    valid_rams = {4, 8, 12, 16, 24, 32, 64}

    explicit = re.search(
        r"\b(4|8|12|16|24|32|64)\s*gb\s*(?:\([^)]*\)\s*)?(?:ddr[45]|lpddr[45]x?|ram)\b", t
    )
    if explicit:
        return int(explicit.group(1))

    slash = re.search(
        r"\b(4|8|12|16|24|32|64)\s*(?:gb)?\s*/\s*(?:128|256|512|1024|1|2)\s*(?:gb|tb)\b", t
    )
    if slash:
        return int(slash.group(1))

    cleaned = re.sub(r"(?:rtx|gtx|rx|vram|graphics)\s*\d{3,4}\s*\d*\s*gb", "", t)
    for m in re.finditer(r"\b(\d{1,2})\s*gb\b", cleaned):
        val = int(m.group(1))
        if val in valid_rams:
            return val

    return None


def extract_ssd_gb(text: str) -> Optional[int]:
    t = text.lower()
    tb_match = re.search(r"\b([12])\s*tb\b", t)
    if tb_match:
        return int(tb_match.group(1)) * 1024

    valid_ssds = {128, 256, 512, 1024}
    for m in re.finditer(r"\b(128|256|512|1024)\s*gb\b", t):
        val = int(m.group(1))
        if val in valid_ssds:
            return val

    return None


def extract_gpu(text: str) -> Optional[str]:
    t = text.lower()
    gpu_match = re.search(r"\b(rtx|gtx|rx)\s*(\d{4})\s*(ti|super)?\b", t)
    if gpu_match:
        prefix = gpu_match.group(1).upper()
        num = gpu_match.group(2)
        suffix = (gpu_match.group(3) or "").upper()
        return f"{prefix} {num}{suffix}".strip()
    return None


def parse_laptop_specs(name: str) -> LaptopSpecs:
    normalized = re.sub(r"[^a-z0-9\s\-\.]", " ", name.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()

    cpu_brand, cpu_model = extract_cpu(name)

    return LaptopSpecs(
        raw_name=name.strip(),
        normalized_name=normalized,
        sku=extract_sku(name),
        series=extract_series(name),
        cpu_brand=cpu_brand,
        cpu_model=cpu_model,
        ram_gb=extract_ram_gb(name),
        ssd_gb=extract_ssd_gb(name),
        gpu=extract_gpu(name),
    )
