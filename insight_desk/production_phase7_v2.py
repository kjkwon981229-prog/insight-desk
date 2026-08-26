from __future__ import annotations

"""Scope the Phase 4 generation authority change to the production call only."""

from contextlib import contextmanager
from types import ModuleType

import insight_desk.generation as generation_module
import insight_desk.generation_pipeline as generation_pipeline_module


_ORIGINAL_GENERATION_STORY_ADMISSION = generation_module.validate_story_admission
_ORIGINAL_PIPELINE_STORY_ADMISSION = generation_pipeline_module.validate_story_admission


def _no_story_readmission(*_args, **_kwargs) -> None:
    return None


@contextmanager
def _production_generation_authority():
    generation_module.validate_story_admission = _no_story_readmission
    generation_pipeline_module.validate_story_admission = _no_story_readmission
    try:
        yield
    finally:
        generation_module.validate_story_admission = _ORIGINAL_GENERATION_STORY_ADMISSION
        generation_pipeline_module.validate_story_admission = _ORIGINAL_PIPELINE_STORY_ADMISSION


def scope_phase7_story_readmission(core_module: ModuleType) -> None:
    """Keep StoryAdmission available to historical tests but non-authoritative in production."""

    # production_orchestrator_v2 installs a temporary global no-op. Restore the ordinary module
    # contract immediately, then suppress only around the one production Phase7 invocation.
    generation_module.validate_story_admission = _ORIGINAL_GENERATION_STORY_ADMISSION
    generation_pipeline_module.validate_story_admission = _ORIGINAL_PIPELINE_STORY_ADMISSION

    current = core_module.produce_phase7_entry_candidate
    if getattr(current, "_insight_desk_v2_scoped", False):
        return

    def produce_phase7_v2(*args, **kwargs):
        with _production_generation_authority():
            return current(*args, **kwargs)

    produce_phase7_v2._insight_desk_v2_scoped = True
    core_module.produce_phase7_entry_candidate = produce_phase7_v2
