from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from insight_desk.core import VerificationCheck


LOCAL_NLI_MODEL = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
LOCAL_NLI_VERIFIER_ID = "local-nli"


EntailmentPredictor = Callable[[str, str], bool]


@dataclass(slots=True)
class LocalNliVerifier:
    predictor: EntailmentPredictor
    verifier_id: str = LOCAL_NLI_VERIFIER_ID
    model_id: str = LOCAL_NLI_MODEL

    @classmethod
    def transformers_default(cls) -> "LocalNliVerifier":
        """Create the measured local verifier with lazy optional imports.

        Torch/transformers are intentionally not core package dependencies. The scheduled runtime
        may install the pinned CPU stack before choosing this constructor; normal imports and CI stay
        lightweight and network-free.
        """

        import torch  # type: ignore[import-not-found]
        from transformers import (  # type: ignore[import-not-found]
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )

        tokenizer = AutoTokenizer.from_pretrained(LOCAL_NLI_MODEL)
        model = AutoModelForSequenceClassification.from_pretrained(LOCAL_NLI_MODEL)
        model.eval()
        labels = [
            model.config.id2label[index].lower() for index in range(model.config.num_labels)
        ]

        def predict(premise: str, hypothesis: str) -> bool:
            encoded = tokenizer(
                premise,
                hypothesis,
                truncation=True,
                return_tensors="pt",
            )
            with torch.no_grad():
                probabilities = torch.softmax(model(**encoded).logits[0], dim=-1).tolist()
            predicted = labels[max(range(len(probabilities)), key=probabilities.__getitem__)]
            return predicted == "entailment"

        return cls(predictor=predict)

    def verify(
        self,
        *,
        check_id: str,
        claim_text: str,
        evidence_text: str,
        evidence_ids: tuple[str, ...],
    ) -> VerificationCheck:
        try:
            entailed = bool(self.predictor(evidence_text, claim_text))
            return VerificationCheck(
                check_id=check_id,
                verifier_id=self.verifier_id,
                model_id=self.model_id,
                evidence_ids=evidence_ids,
                entailed=entailed,
                zero_cost=True,
            )
        except Exception as exc:
            error_name = type(exc).__name__.lower()[:80] or "unknown"
            return VerificationCheck(
                check_id=check_id,
                verifier_id=self.verifier_id,
                model_id=self.model_id,
                evidence_ids=evidence_ids,
                entailed=None,
                error_code=f"local_model_error:{error_name}",
                zero_cost=True,
            )
