"""运行级产物溯源。

设计见 docs/provenance.md。
"""
from .run import (
    SEAL_MARKER,
    STAGE_TOKENS,
    RunContext,
    git_state,
    iter_events,
    load_manifest,
    sha256_file,
    tool_versions,
)

__all__ = [
    "SEAL_MARKER",
    "STAGE_TOKENS",
    "RunContext",
    "git_state",
    "iter_events",
    "load_manifest",
    "sha256_file",
    "tool_versions",
]
