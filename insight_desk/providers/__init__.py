"""Zero-cost production provider adapters for the rebuilt Insight Desk engine."""

from .cloudflare import CLOUDFLARE_MODEL, CLOUDFLARE_VERIFIER_ID, CloudflareClaimVerifier
from .groq import ALLOWED_GROQ_MODELS, GROQ_20B, GROQ_120B, GroqFreeClient
from .local_nli import LOCAL_NLI_MODEL, LOCAL_NLI_VERIFIER_ID, LocalNliVerifier
from .transport import JsonHttpTransport, ProviderConfigError, ProviderTransportError

__all__ = [
    "ALLOWED_GROQ_MODELS",
    "CLOUDFLARE_MODEL",
    "CLOUDFLARE_VERIFIER_ID",
    "CloudflareClaimVerifier",
    "GROQ_20B",
    "GROQ_120B",
    "GroqFreeClient",
    "JsonHttpTransport",
    "LOCAL_NLI_MODEL",
    "LOCAL_NLI_VERIFIER_ID",
    "LocalNliVerifier",
    "ProviderConfigError",
    "ProviderTransportError",
]
