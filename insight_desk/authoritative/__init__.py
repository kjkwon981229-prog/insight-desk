"""Optional authoritative evidence adapters.

The package is deliberately separate from the NAVER discovery path.  An
adapter may strengthen a candidate, but it never creates a story by itself.
"""

from .config import AuthorityConfig, load_authority_config
from .router import AuthorityReport, AuthoritativeRouter, build_authoritative_router

__all__ = [
    "AuthorityConfig",
    "AuthorityReport",
    "AuthoritativeRouter",
    "build_authoritative_router",
    "load_authority_config",
]
