from __future__ import annotations

import re

# 마침표·물음표·느낌표 뒤(닫는 따옴표·괄호 허용)에 공백이 있고, 다음 글자가 문장 시작처럼 보일 때만 경계로 본다.
# 소수점(3.2)은 뒤에 공백이 없으므로 경계가 아니다.
_BOUNDARY = re.compile(r"(?<=[.!?])([\"'”’)\]]*)[ \t]+(?=[\"'“‘(\[「]?[A-Z가-힣0-9])")
_ABBREVIATIONS = frozenset(
    {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "inc", "ltd", "corp", "no"}
)
_MIN_SENTENCE_CHARS = 8


def _is_abbreviation(prefix: str) -> bool:
    token = prefix.rstrip().rsplit(None, 1)[-1] if prefix.strip() else ""
    token = token.lstrip("\"'“‘([「")
    if not token.endswith("."):
        return False
    if re.fullmatch(r"(?:[A-Za-z]\.)+", token):
        return True
    return token[:-1].lower() in _ABBREVIATIONS


def _split_block(block: str) -> list[str]:
    pieces: list[str] = []
    start = 0
    for match in _BOUNDARY.finditer(block):
        punct_end = match.start()
        if block[punct_end - 1] == "." and _is_abbreviation(block[start:punct_end]):
            continue
        cut = match.start(1) + len(match.group(1))
        pieces.append(block[start:cut])
        start = match.end()
    pieces.append(block[start:])
    return pieces


def split_sentences(
    body: str,
    *,
    max_sentences: int = 40,
    max_chars: int = 6000,
) -> tuple[str, ...]:
    """본문을 번호를 붙일 수 있는 문장 목록으로 나눈다(순서 유지, 중복·짧은 조각 제외)."""
    sentences: list[str] = []
    seen: set[str] = set()
    total_chars = 0
    for line in body.splitlines():
        if not line.strip():
            continue
        for piece in _split_block(line.strip()):
            sentence = " ".join(piece.split())
            if len(sentence) < _MIN_SENTENCE_CHARS or sentence in seen:
                continue
            if sentences and total_chars + len(sentence) > max_chars:
                return tuple(sentences)
            seen.add(sentence)
            sentences.append(sentence)
            total_chars += len(sentence)
            if len(sentences) >= max_sentences:
                return tuple(sentences)
    return tuple(sentences)
