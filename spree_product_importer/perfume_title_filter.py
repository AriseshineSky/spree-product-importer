import re

# Latin-script keywords: word-boundary match (case insensitive).
_LATIN_WORDS = (
    # English
    "perfume",
    "cologne",
    "fragrance",
    "parfum",
    # Spanish / Portuguese (shared forms)
    "fragancia",
    "fragrancia",
    "colonia",
    # Portuguese
    "fragrância",
    "colônia",
    # Turkish (ASCII forms; parfüm handled below)
    "parfum",
    "kolonya",
    "esans",
)

_LATIN_PHRASES = (
    "eau de parfum",
    "eau de toilette",
)

# CJK / kana: substring match.
_CJK_KEYWORDS = (
    # Chinese
    "香水",
    "淡香水",
    "古龙水",
    "香精",
    "香氛",
    # Japanese
    "オードパルファム",
    "オードトワレ",
    "フレグランス",
    "パルファム",
)

_TURKISH_KEYWORDS = (
    "parfüm",
    "parfum",
)

_latin_pattern = re.compile(
    r"(?:"
    + "|".join(re.escape(phrase) for phrase in _LATIN_PHRASES)
    + r")"
    r"|\b(?:"
    + "|".join(re.escape(word) for word in _LATIN_WORDS)
    + r")\b",
    re.IGNORECASE,
)


def title_contains_perfume_keyword(title: str) -> bool:
    if not title:
        return False

    if _latin_pattern.search(title):
        return True

    title_lower = title.lower()
    for keyword in _TURKISH_KEYWORDS:
        if keyword in title_lower:
            return True

    for keyword in _CJK_KEYWORDS:
        if keyword in title:
            return True

    return False


def is_perfume_from_product_titles(prod: dict) -> bool:
    for key in ("title", "title_en"):
        title = prod.get(key)
        if title and title_contains_perfume_keyword(title):
            return True
    return False
