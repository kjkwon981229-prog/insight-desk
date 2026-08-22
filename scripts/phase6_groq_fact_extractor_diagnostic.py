from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from insight_desk.core import RawArticle, SourceProvenance
from insight_desk.semantic import (
    FACT_EXTRACTION_SCHEMA,
    EvidenceSegmenter,
    FactExtractionRequest,
    Groq20BFactExtractor,
)


ROOT = Path(__file__).resolve().parents[1]
CASE_ID = "run95-explicit-lineup"
GOLD_TOKENS = ("한화", "두산", "왕옌청", "곽빈")


def main() -> int:
    suite = json.loads((ROOT / "benchmarks/run94_95_semantic.json").read_text(encoding="utf-8"))
    case = next(item for item in suite["cases"] if item["id"] == CASE_ID)
    title = case["input"]["title"]
    article = RawArticle(
        article_id=f"benchmark:{CASE_ID}",
        provenance=SourceProvenance(
            source_id="benchmark:clean-room",
            source_name="Insight Desk clean-room benchmark",
            url=f"https://example.invalid/benchmark/{CASE_ID}",
            retrieved_via="locked_benchmark_fixture",
            fetched_at=datetime(2026, 8, 23, 4, 0, tzinfo=timezone.utc),
        ),
        title=title,
        body=title,
        topic_ids=("kbo_hanwha",),
        query=None,
    )
    request = FactExtractionRequest(
        article=article,
        topic_id="kbo_hanwha",
        evidence=EvidenceSegmenter().segment(article),
    )
    extractor = Groq20BFactExtractor.from_env(delay_seconds=0.0)
    response = extractor.client.structured_json(
        prompt=extractor._prompt(request),
        schema=FACT_EXTRACTION_SCHEMA,
        schema_name="insight_desk_fact_extract_v1",
        system_prompt=(
            "Extract only explicit event facts from the supplied evidence. "
            "Use no outside knowledge. Follow the JSON schema exactly and output no commentary."
        ),
    )

    evidence_by_id = {span.evidence_id: span.text for span in request.evidence}
    diagnostic = []
    for index, fact in enumerate(response.get("facts", []), start=1):
        cited_text = "\n".join(
            evidence_by_id[evidence_id]
            for evidence_id in fact.get("evidence_ids", [])
            if evidence_id in evidence_by_id
        )
        participants = fact.get("participants", [])
        diagnostic.append(
            {
                "fact_index": index,
                "subject": fact.get("subject"),
                "object": fact.get("object"),
                "participants": participants,
                "participant_checks": [
                    {
                        "value": participant,
                        "source_literal": participant in cited_text,
                        "contains_locked_gold_token": any(token in participant for token in GOLD_TOKENS),
                    }
                    for participant in participants
                ],
            }
        )

    print(
        json.dumps(
            {
                "case_id": CASE_ID,
                "provider_calls": 1,
                "facts": diagnostic,
                "logged_article_body": False,
                "logged_credentials": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
