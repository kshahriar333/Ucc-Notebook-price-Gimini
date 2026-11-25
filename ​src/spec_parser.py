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


# Common Acer SKU / Part Number patterns
# Examples: A315-59-562P, AN515-58-57Y8, ANV15-51-532J, SFG14-71-505P, PHN16-71-73LT, NX.K6TSI.002, NH.QM0SI.001
SKU_PATTERNS = [
    r"(?:NX|NH|UN)\.[A-Z0-9]{5}\.[A-Z0-9]{3}",  # Acer Part Number (NX.XXXXX.XXX)
    r"(?:A[1357]|ANV?|SF[G357X]?|PHN?|PT[3579]?|TMP?|TMB?|EX[2]?|CB[357]?|SP[135]?)\d{2,3}-\d{2,3}[A-Z]?-[A-Z0-9]{3,5}",  # Full model e.g. ANV15-51-532J
    r"(?:A[1357]|ANV?|SF[G357X]?|PHN?|PT[3579]?|TMP?|TMB?|EX[2]?|CB[357]?|SP[135]?)\d{2,3}-\d{2,3}[A-Z]?",  # Base chassis e.g. A315-59, AN515-58
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
        if re.search(r"" + re.escape(s) + r"", lower_text):
            return s.title()
    return None


def extract_cpu(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Extracts normalized CPU brand & exact CPU model code.
    Handles Intel Core i3/i5/i7/i9, Core Ultra 5/7/9, Intel N100/N200, Celeron,
    and AMD Ryzen 3/5/7/9 (e.g., 7520U, 5500U, 7735HS, 8845HS).
    """
    t = text.lower()

    # Intel Core Ultra (e.g., Core Ultra 7 155H, Ultra 5 125H)
    ultra_match = re.search(r"ultra\s*([579])\s*(\d{3}[a-z]{1,2})?", t)
    if ultra_match:
        tier = ultra_match.group(1)
        code = ultra_match.group(2) or ""
        return ("Intel", f"ultra-{tier}-{code}".strip("-").upper())

    # Intel Core i3/i5/i7/i9 (e.g., i5-1235U, i5 13420H, i7-13620H, Core 5 120U)
    intel_match = re.search(
        r"(?:core\s*)?(i[3579]|core\s*[357])\s*[-\s]?\s*(\d{4,5}[a-z]{0,2})", t
    )
    if intel_match:
        tier = intel_match.group(1).replace(" ", "")
        code = intel_match.group(2).upper()
        return ("Intel", f"{tier}-{code}")

    # Fallback Intel tier without exact model number (e.g., "12th Gen Core i5")
    intel_tier_only = re.search(r"(i[3579])", t)
    gen_match = re.search(r"(1[0-4])(?:th|nd|rd|st)\s*gen", t)
    if intel_tier_only:
        gen_str = f"{gen_match.group(1)}th" if gen_match else ""
        return ("Intel", f"{intel_tier_only.group(1)}-{gen_str}".strip("-"))

    # Intel N-series / Celeron (e.g., N100, N200, N4500)
    n_series = re.search(r"(?:celeron\s*)?(n\d{3,4})", t)
    if n_series:
        return ("Intel", n_series.group(1).upper())

    # AMD Ryzen (e.g., Ryzen 5 7520U, Ryzen 7 7735HS, R5 5500U)
    ryzen_match = re.search(
        r"(?:ryzen|r)\s*([3579])\s*[-\s]?\s*(\d{4}[a-z]{0,2})", t
    )
    if ryzen_match:
        tier = ryzen_match.group(1)
        code = ryzen_match.group(2).upper()
        return ("AMD", f"R{tier}-{code}")

    ryzen_tier_only = re.search(r"ryzen\s*([3579])", t)
    if ryzen_tier_only:
        return ("AMD", f"R{ryzen_tier_only.group(1)}")

    return (None, None)


def extract_ram_gb(text: str) -> Optional[int]:
    """
    Extracts RAM size in GB (e.g., 8GB RAM, 16GB DDR5, 8GB/512GB).
    Valid RAM sizes: 4, 8, 12, 16, 24, 32, 64.
    """
    t = text.lower()
    valid_rams = {4, 8, 12, 16, 24, 32, 64}

    # Explicit RAM mention: "16GB RAM", "8GB DDR4", "16 GB LPDDR5"
    explicit = re.search(
        r"(4|8|12|16|24|32|64)\s*gb\s*(?:ddr[45]|lpddr[45]x?|ram)", t
    )
    if explicit:
        return int(explicit.group(1))

    # Slash notation: "8GB/512GB" or "16/512GB"
    slash = re.search(r"(4|8|12|16|24|32|64)\s*(?:gb)?\s*/\s*(?:128|256|512|1024|1|2)\s*(?:gb|tb)", t)
    if slash:
        return int(slash.group(1))

    # General standalone GB values matching standard RAM sizes (excluding VRAM like RTX 4060 8GB)
    cleaned = re.sub(r"(?:rtx|gtx|rx|vram|graphics)\s*\d{3,4}\s*\d*\s*gb", "", t)
    for m in re.finditer(r"(\d{1,2})\s*gb", cleaned):
        val = int(m.group(1))
        if val in valid_rams:
            return val

    return None


def extract_ssd_gb(text: str) -> Optional[int]:
    """
    Extracts storage size normalized to GB (e.g., 512GB -> 512, 1TB -> 1024, 2TB -> 2048).
    """
    t = text.lower()

    # Check TB first (1TB, 2TB)
    tb_match = re.search(r"([12])\s*tb", t)
    if tb_match:
        return int(tb_match.group(1)) * 1024

    # Check GB SSD / NVMe / Storage
    valid_ssds = {128, 256, 512, 1024}
    for m in re.finditer(r"(128|256|512|1024)\s*gb", t):
        val = int(m.group(1))
        if val in valid_ssds:
            return val

    return None


def extract_gpu(text: str) -> Optional[str]:
    """Extracts dedicated GPU model if present (e.g., RTX 4050, RTX 3050, GTX 1650)."""
    t = text.lower()
    gpu_match = re.search(r"(rtx|gtx|rx)\s*(\d{4})\s*(ti|super)?", t)
    if gpu_match:
        prefix = gpu_match.group(1).upper()
        num = gpu_match.group(2)
        suffix = (gpu_match.group(3) or "").upper()
        return f"{prefix} {num}{suffix}".strip()
    return None


def parse_laptop_specs(name: str) -> LaptopSpecs:
    normalized = re.sub(r"[^a-z0-9\s\-\.]", " ", name.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()

    sku = extract_sku(name)
    series = extract_series(name)
    cpu_brand, cpu_model = extract_cpu(name)
    ram_gb = extract_ram_gb(name)
    ssd_gb = extract_ssd_gb(name)
    gpu = extract_gpu(name)

    return LaptopSpecs(
        raw_name=name.strip(),
        normalized_name=normalized,
        sku=sku,
        series=series,
        cpu_brand=cpu_brand,
        cpu_model=cpu_model,
        ram_gb=ram_gb,
        ssd_gb=ssd_gb,
        gpu=gpu,
    )
