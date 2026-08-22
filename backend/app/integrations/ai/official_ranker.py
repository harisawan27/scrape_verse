import re
from urllib.parse import urlparse
from app.integrations.ai.types import SearchCandidate

KNOWN_AGGREGATORS = {
    "academicjobs.com",
    "indeed.com",
    "glassdoor.com",
    "linkedin.com",
    "kariyer.net",
    "jobsearch.com",
    "scholarshipportal.com",
    "findascholarship.com",
    "wikipedia.org",
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "pinterest.com",
    "reddit.com",
}

OFFICIAL_TLDS = {".edu.tr", ".edu", ".gov.tr", ".gov", ".ac.uk", ".org.tr"}


class OfficialSourceRanker:
    """
    Ranks discovered URLs to enforce first-party official source priority.
    Prevents third-party job boards (e.g. academicjobs.com) or aggregator SEO sites
    from being chosen as primary watch targets when credible first-party sources exist.
    """

    @classmethod
    def rank_candidates(cls, query: str, candidates: list[SearchCandidate]) -> list[SearchCandidate]:
        """Rank candidates according to first-party official authority."""
        if not candidates:
            return []

        query_lower = query.lower()
        scored: list[tuple[int, SearchCandidate]] = []

        for cand in candidates:
            score = cls.calculate_score(query_lower, cand)
            cand.priority_score = score
            cand.is_official = score >= 70
            scored.append((score, cand))

        # Sort descending by priority score
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored]

    @classmethod
    def calculate_score(cls, query_lower: str, cand: SearchCandidate) -> int:
        score = 50
        parsed = urlparse(cand.url)
        netloc = parsed.netloc.lower()
        path = parsed.path.lower()
        title_lower = cand.title.lower()

        # 1. Check if domain is a known third-party aggregator / social platform
        is_aggregator = any(agg in netloc for agg in KNOWN_AGGREGATORS)
        if is_aggregator:
            score -= 35  # heavily penalize aggregators

        # 2. Extract brand clues from query (e.g., "bahçeşehir" -> "bau", "istanbul", "daraz")
        brand_tokens = []
        if "bahçeşehir" in query_lower or "bahcesehir" in query_lower or "bau" in query_lower:
            brand_tokens.extend(["bau.edu.tr", "bau", "bahcesehir", "bahçeşehir"])
        if "istanbul" in query_lower:
            brand_tokens.extend(["istanbul.edu.tr", "istanbul.edu", "istanbul"])
        if "daraz" in query_lower:
            brand_tokens.extend(["daraz.pk", "daraz"])

        # 3. First-party brand matching in domain
        matched_brand = any(tok in netloc for tok in brand_tokens)
        if matched_brand:
            score += 40

        # 4. Official Educational / Government TLD
        if any(netloc.endswith(tld) or tld in netloc for tld in OFFICIAL_TLDS):
            score += 25

        # 5. Targeted functional path matching (careers, admissions, scholarships)
        if any(k in path for k in ["career", "job", "kariyer", "ik", "human-resources"]):
            cand.target_type = "careers"
            if "job" in query_lower or "career" in query_lower:
                score += 15
        elif any(k in path for k in ["scholarship", "burs", "financial-aid"]):
            cand.target_type = "scholarships"
            if "scholarship" in query_lower or "burs" in query_lower:
                score += 15
        elif any(k in path for k in ["admission", "ogrenci", "apply"]):
            cand.target_type = "admissions"
            if "admission" in query_lower or "apply" in query_lower:
                score += 15
        elif any(k in path for k in ["contact", "iletisim", "about"]):
            cand.target_type = "contact"
        elif "daraz.pk/products" in cand.url or "/product" in path:
            cand.target_type = "product"
            score += 20

        # 6. Official portal keyword in title
        if any(k in title_lower for k in ["official", "rectorate", "university", "careers", "admissions"]):
            score += 10

        return max(0, min(100, score))
