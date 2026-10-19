from __future__ import annotations

import re
import unicodedata


_STOPWORDS_KO = frozenset({
    "그리고", "하지만", "있다", "했다", "한다", "이번", "지난",
    "관련", "대한", "통해", "위해",
})

_STOPWORDS_EN = frozenset({
    "the", "and", "for", "with", "that", "this", "from", "are", "was",
    "were", "been", "have", "has", "had", "but", "not", "you", "all",
    "can", "her", "his", "one", "our", "out", "its",
})

_JOSA_SUFFIXES = (
    "에서", "으로", "은", "는", "이", "가", "을", "를",
    "의", "에", "와", "과", "도", "로",
)

_TOKEN_RE = re.compile(r"[a-z0-9\uac00-\ud7af]+")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def content_words(text: str) -> frozenset[str]:
    norm = normalize(text)
    raw_tokens = _TOKEN_RE.findall(norm)
    result: set[str] = set()
    for tok in raw_tokens:
        if len(tok) < 2:
            continue
        if tok in _STOPWORDS_KO or tok in _STOPWORDS_EN:
            continue
        processed = tok
        if re.search(r"[\uac00-\ud7af]", tok):
            for josa in _JOSA_SUFFIXES:
                if tok.endswith(josa) and len(tok) >= len(josa) + 2:
                    processed = tok[: len(tok) - len(josa)]
                    break
        if len(processed) >= 2 and processed not in _STOPWORDS_KO and processed not in _STOPWORDS_EN:
            result.add(processed)
    return frozenset(result)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0
