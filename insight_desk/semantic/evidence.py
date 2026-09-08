from __future__ import annotations

from dataclasses import dataclass

from insight_desk.core import EvidenceField, EvidenceSpan, RawArticle


@dataclass(frozen=True, slots=True)
class EvidenceSegmenter:
    """Split source text into bounded, exact-offset evidence windows.

    This is intentionally not an NLP sentence segmenter. It only chooses source-aligned windows
    and never normalizes or paraphrases source text. Every returned EvidenceSpan can therefore be
    revalidated directly against the immutable RawArticle body.
    """

    max_chars: int = 1800

    def __post_init__(self) -> None:
        if self.max_chars < 80:
            raise ValueError("max_chars must be >= 80")

    def segment(self, article: RawArticle) -> tuple[EvidenceSpan, ...]:
        source = article.body
        if not source.strip():
            return ()

        spans: list[EvidenceSpan] = []
        cursor = 0
        index = 1
        source_len = len(source)

        while cursor < source_len:
            while cursor < source_len and source[cursor].isspace():
                cursor += 1
            if cursor >= source_len:
                break

            hard_end = min(source_len, cursor + self.max_chars)
            end = hard_end
            if hard_end < source_len:
                end = self._best_break(source, cursor, hard_end)

            while end > cursor and source[end - 1].isspace():
                end -= 1
            if end <= cursor:
                end = hard_end

            span = EvidenceSpan.from_article(
                evidence_id=f"ev:{article.article_id}:{index:04d}",
                article=article,
                field=EvidenceField.BODY,
                start=cursor,
                end=end,
            )
            spans.append(span)
            index += 1
            cursor = end

        return tuple(spans)

    @staticmethod
    def _best_break(source: str, start: int, hard_end: int) -> int:
        """Prefer paragraph/newline/space boundaries without exceeding max_chars."""

        lower_bound = start + max(1, (hard_end - start) // 2)
        for token in ("\n\n", "\n", " "):
            position = source.rfind(token, lower_bound, hard_end + 1)
            if position >= lower_bound:
                return position + (len(token) if token != " " else 0)
        return hard_end
