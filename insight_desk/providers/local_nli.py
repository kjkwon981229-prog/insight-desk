from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from insight_desk.core import VerificationCheck


LOCAL_NLI_MODEL = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
LOCAL_NLI_FALLBACK_MODEL = "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli"
LOCAL_NLI_VERIFIER_ID = "local-nli"
LOCAL_NLI_FALLBACK_ROUTE_ID = "local-nli-minilm"


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
        """Create the measured mDeBERTa verifier with optional runtime imports."""
        return cls.transformers_model(
            LOCAL_NLI_MODEL,
            verifier_id=LOCAL_NLI_VERIFIER_ID,
        )

    @classmethod
    def transformers_fallback(cls) -> "LocalNliVerifier":
        """Create the independent smaller multilingual NLI fallback route."""
        return cls.transformers_model(
            LOCAL_NLI_FALLBACK_MODEL,
            verifier_id=LOCAL_NLI_FALLBACK_ROUTE_ID,
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


@dataclass(slots=True)
class LazyLocalNliVerifier:
    """Load a transformers NLI route only if failover actually reaches it."""

    model_id: str = LOCAL_NLI_FALLBACK_MODEL
    verifier_id: str = LOCAL_NLI_FALLBACK_ROUTE_ID
    _delegate: LocalNliVerifier | None = field(default=None, init=False, repr=False)

    def verify(
        self,
        *,
        check_id: str,
        claim_text: str,
        evidence_text: str,
        evidence_ids: tuple[str, ...],
    ) -> VerificationCheck:
        if self._delegate is None:
            try:
                self._delegate = LocalNliVerifier.transformers_model(
                    self.model_id,
                    verifier_id=self.verifier_id,
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
        return self._delegate.verify(
            check_id=check_id,
            claim_text=claim_text,
            evidence_text=evidence_text,
            evidence_ids=evidence_ids,
        )
