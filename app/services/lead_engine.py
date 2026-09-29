import re
import hashlib
from app.models.office_lead import CommercialModel, LeadTier

def generate_dedup_hash(email: str, phone: str | None) -> str:
    """Generates an immutable SHA-256 fingerprint from sanitized email and phone."""
    clean_email = email.strip().lower()
    clean_phone = re.sub(r"\D", "", phone)[-10:] if phone else "NOPHONE"
    raw_key = f"{clean_email}:{clean_phone}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

def calculate_lead_score(
    commercial_model: CommercialModel,
    volume_estimate: str | None,
    country: str,
    email: str,
    phone: str | None,
) -> tuple[int, LeadTier]:
    """
    Computes priority qualification score (0-100) and assigns lead tier[cite: 1, 2].
    HOT: >= 70 | WARM: 40-69 | COLD: < 40
    """
    score = 0

    # 1. Commercial Model Base Weight
    if commercial_model == CommercialModel.STATE_OWNERSHIP:
        score += 35
    elif commercial_model == CommercialModel.DISTRIBUTION:
        score += 30
    elif commercial_model == CommercialModel.PRIVATE_LABEL:
        score += 25

    # 2. Volume Estimate Intent Evaluation
    if volume_estimate:
        vol_lower = volume_estimate.lower()
        if any(term in vol_lower for term in ["container", "fcl", "40ft", "20ft"]):
            score += 35
            match = re.search(r"(\d+)", vol_lower)
            if match and int(match.group(1)) >= 5:
                score += 10
        elif any(term in vol_lower for term in ["case", "pallet", "truckload"]):
            score += 20
        else:
            score += 10

    # 3. Domain & Phone Credibility
    free_domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"]
    domain = email.split("@")[-1].lower() if "@" in email else ""
    if domain and domain not in free_domains:
        score += 15  # Verified corporate domain

    if phone and len(re.sub(r"\D", "", phone)) >= 10:
        score += 10  # Valid direct phone line

    # 4. Strategic Target Footprint
    strategic_corridors = [
        "tanzania", "kenya", "nigeria", "united states", "usa", 
        "united arab emirates", "uae", "canada", "united kingdom", "uk", "india"
    ]
    if country.strip().lower() in strategic_corridors:
        score += 10

    final_score = min(score, 100)
    if final_score >= 70:
        tier = LeadTier.HOT
    elif final_score >= 40:
        tier = LeadTier.WARM
    else:
        tier = LeadTier.COLD

    return final_score, tier