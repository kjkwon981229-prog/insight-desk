from __future__ import annotations

import json

from insight_desk.semantic.tooling import KiwiMorphologyHelper


CASES = (
    "정부가 용인 반도체 산업의 5조원 투자 조기 이행을 지원한다.",
    "코팅솔루션포유가 NVIDIA 협업 프로그램 참여사로 선정됐다.",
    "네오팩토리가 AI 공장 구축 사업을 15억달러에 수주했다.",
    "코스피가 소비자물가 둔화에 3.4% 급등해 마감했다.",
    "한국은행 부총재는 특별한 충격이 없다면 기준금리를 추가 인상할 수 있다고 밝혔다.",
    "한화 이글스와 두산 베어스의 선발이 예고됐다.",
)


def noun_phrase_before_case(text: str, tokens, case_tag: str) -> list[str]:
    out: list[str] = []
    for index, token in enumerate(tokens):
        if token.tag != case_tag or index == 0:
            continue
        j = index - 1
        start = token.start
        while j >= 0 and (tokens[j].tag.startswith("N") or tokens[j].tag in {"SL", "SN"}):
            start = tokens[j].start
            j -= 1
        surface = text[start:token.start].strip()
        if surface:
            out.append(surface)
    return out


def predicate_candidates(tokens) -> list[str]:
    candidates: list[str] = []
    for index, token in enumerate(tokens):
        if token.tag == "XSV" and index > 0 and tokens[index - 1].tag.startswith("N"):
            candidates.append(tokens[index - 1].surface)
        elif token.tag == "VV":
            candidates.append(token.surface)
    return candidates


def main() -> None:
    kiwi = KiwiMorphologyHelper()
    for case_index, text in enumerate(CASES, start=1):
        sentences = kiwi.split_sentences(text)
        if not sentences:
            raise AssertionError(f"Kiwi returned no sentence: {text}")
        for sentence in sentences:
            if sentence.text != text[sentence.start : sentence.end]:
                raise AssertionError("Kiwi sentence lost exact source surface")
        tokens = kiwi.analyze(text)
        subjects = noun_phrase_before_case(text, tokens, "JKS") + noun_phrase_before_case(text, tokens, "JX")
        objects = noun_phrase_before_case(text, tokens, "JKO")
        actions = predicate_candidates(tokens)
        print(
            json.dumps(
                {
                    "case": case_index,
                    "text": text,
                    "sentences": [[s.text, s.start, s.end] for s in sentences],
                    "subjects": subjects,
                    "objects": objects,
                    "actions": actions,
                    "tokens": [
                        [token.surface, token.normalized, token.tag, token.start, token.end]
                        for token in tokens
                    ],
                },
                ensure_ascii=False,
            )
        )
    print("PHASE6_KIWI_FACT_SCAFFOLD_DIAGNOSTIC result=PASS external_api_calls=0 credentials=0 paid_paths=0")


if __name__ == "__main__":
    main()
