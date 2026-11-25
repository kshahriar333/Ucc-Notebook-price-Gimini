from typing import Dict, List, Optional, Tuple
from rapidfuzz import fuzz

from src.spec_parser import LaptopSpecs

# স্টোরভেদে টাইটেল ছোট-বড় হলেও যেন সঠিক স্পেক মিললে ম্যাচ হয়
EFFECTIVE_MIN_SCORE = 62


def compute_match_score(target: LaptopSpecs, candidate: LaptopSpecs) -> Tuple[float, str]:
    """
    Computes a strict spec-aware similarity score (0 to 100) between a UCC laptop
    and a competitor laptop.
    """
    # 1. Exact SKU / Part Number match
    if target.sku and candidate.sku:
        if target.sku == candidate.sku:
            return 100.0, f"Exact SKU ({target.sku})"
        if not target.sku.startswith(("UN.", "NX.", "NH.")) and not candidate.sku.startswith(("UN.", "NX.", "NH.")):
            target_base = "-".join(target.sku.split("-")[:2])
            cand_base = "-".join(candidate.sku.split("-")[:2])
            if len(target_base) >= 5 and target_base != cand_base:
                return 0.0, "SKU Mismatch"

    # 2. Hard Disqualifiers on Core Hardware Specs
    if target.ram_gb and candidate.ram_gb and target.ram_gb != candidate.ram_gb:
        return 0.0, "RAM Mismatch"

    if target.ssd_gb and candidate.ssd_gb and target.ssd_gb != candidate.ssd_gb:
        return 0.0, "SSD Mismatch"

    if target.cpu_model and candidate.cpu_model and target.cpu_model != candidate.cpu_model:
        return 0.0, "CPU Mismatch"

    if target.gpu and candidate.gpu and target.gpu != candidate.gpu:
        return 0.0, "GPU Mismatch"

    # 3. Weighted Scoring
    score = 0.0
    reasons = []

    # Base fuzzy name similarity (up to 40 points)
    name_sim = fuzz.token_set_ratio(target.normalized_name, candidate.normalized_name)
    score += (name_sim / 100.0) * 40.0

    # Series match (15 points)
    if target.series and candidate.series:
        if target.series == candidate.series:
            score += 15.0
            reasons.append(target.series)
        else:
            score -= 10.0

    # CPU exact match bonus (25 points)
    if target.cpu_model and candidate.cpu_model and target.cpu_model == candidate.cpu_model:
        score += 25.0
        reasons.append(target.cpu_model)

    # RAM & SSD exact match bonus (15 points)
    if target.ram_gb and candidate.ram_gb and target.ram_gb == candidate.ram_gb:
        score += 7.5
        reasons.append(f"{target.ram_gb}GB")
    if target.ssd_gb and candidate.ssd_gb and target.ssd_gb == candidate.ssd_gb:
        score += 7.5
        reasons.append(f"{target.ssd_gb}GB SSD")

    # GPU match bonus (10 points)
    if target.gpu and candidate.gpu and target.gpu == candidate.gpu:
        score += 10.0
        reasons.append(target.gpu)

    # Partial SKU chassis bonus (15 points)
    if target.sku and candidate.sku:
        t_parts = target.sku.split("-")
        c_parts = candidate.sku.split("-")
        if len(t_parts) >= 2 and len(c_parts) >= 2 and t_parts[:2] == c_parts[:2]:
            score += 15.0
            reasons.append(f"Chassis {'-'.join(t_parts[:2])}")

    final_score = min(100.0, max(0.0, score))
    reason_str = ", ".join(reasons) if reasons else f"Fuzzy ({int(name_sim)}%)"
    return final_score, reason_str


def find_best_store_match(
    ucc_product: dict,
    store_products: List[dict],
    min_score: int = EFFECTIVE_MIN_SCORE,
) -> Optional[dict]:
    target_specs: LaptopSpecs = ucc_product["specs"]
    best_item = None
    best_score = 0.0
    best_reason = ""

    for cand in store_products:
        score, reason = compute_match_score(target_specs, cand["specs"])
        if score >= min_score and score > best_score:
            best_score = score
            best_item = cand
            best_reason = reason

    if best_item:
        matched = dict(best_item)
        matched["match_score"] = round(best_score, 1)
        matched["match_reason"] = best_reason
        return matched
    return None


def compare_acer_catalog(
    store_data: Dict[str, List[dict]],
    query: Optional[str] = None,
    only_matched: bool = False,
) -> List[dict]:
    """
    Compares every Acer laptop listed on UCC against StarTech, Ryans, and Techland.
    """
    ucc_items = store_data.get("UCC", [])
    startech_items = store_data.get("StarTech", [])
    ryans_items = store_data.get("Ryans", [])
    techland_items = store_data.get("Techland", [])

    comparisons = []
    q_tokens = query.lower().split() if query else []

    for ucc in ucc_items:
        if q_tokens:
            haystack = ucc["name"].lower()
            if not all(tok in haystack for tok in q_tokens):
                continue

        st_match = find_best_store_match(ucc, startech_items)
        ry_match = find_best_store_match(ucc, ryans_items)
        tl_match = find_best_store_match(ucc, techland_items)

        has_any_match = any([st_match, ry_match, tl_match])
        if only_matched and not has_any_match:
            continue

        price_candidates = []
        if ucc["price_num"]:
            price_candidates.append(("UCC", ucc["price_num"]))
        if st_match and st_match["price_num"]:
            price_candidates.append(("StarTech", st_match["price_num"]))
        if ry_match and ry_match["price_num"]:
            price_candidates.append(("Ryans", ry_match["price_num"]))
        if tl_match and tl_match["price_num"]:
            price_candidates.append(("Techland", tl_match["price_num"]))

        lowest_store = None
        lowest_price = None
        if price_candidates:
            lowest_store, lowest_price = min(price_candidates, key=lambda x: x[1])

        comparisons.append({
            "ucc": ucc,
            "StarTech": st_match,
            "Ryans": ry_match,
            "Techland": tl_match,
            "lowest_store": lowest_store,
            "lowest_price": lowest_price,
        })

    return comparisons
