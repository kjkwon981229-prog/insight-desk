from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from insight_desk.core import VerificationCheck


LOCAL_NLI_MODEL = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
LOCAL_NLI_VERIFIER_ID = "local-nli"


EntailmentPredictor = Callable[[str, str], bool]


def _transformers_predictor(model_id: str) -> EntailmentPredictor:
    import torch  # type: ignore[import-not-found]
    from transformers import (  # type: ignore[import-not-found]
        AutoModelForSequenceClassification,
        AutoTokenizer,
    )

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForSequenceClassification.from_pretrained(model_id)
    model.eval()
    labels = [
        model.config.id2label[index].lower() for index in range(model.config.num_labels)
    ]
    if "entailment" not in labels:
        raise ValueError(f"local NLI model has no entailment label: {model_id}")

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

    return predict


def _lazy_transformers_predictor(model_id: str) -> EntailmentPredictor:
    """Defer model/runtime loading until the local verifier is actually needed."""

    delegate: EntailmentPredictor | None = None

    def predict(premise: str, hypothesis: str) -> bool:
        nonlocal delegate
        if delegate is None:
            delegate = _transformers_predictor(model_id)
        return delegate(premise, hypothesis)

    return predict


@dataclass(slots=True)
class LocalNliVerifier:
    predictor: EntailmentPredictor
    verifier_id: str = LOCAL_NLI_VERIFIER_ID
    model_id: str = LOCAL_NLI_MODEL

    @classmethod
    def transformers_model(
        cls,
        model_id: str,
        *,
        verifier_id: str,
    ) -> "LocalNliVerifier":
        return cls(
            predictor=_transformers_predictor(model_id),
            verifier_id=verifier_id,
            model_id=model_id,
        )

    @classmethod
    def transformers_default(cls) -> "LocalNliVerifier":
        """Create the measured mDeBERTa verifier without eager runtime/model loading."""
        return cls(
            predictor=_lazy_transformers_predictor(LOCAL_NLI_MODEL),
            verifier_id=LOCAL_NLI_VERIFIER_ID,
            model_id=LOCAL_NLI_MODEL,
        )

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
