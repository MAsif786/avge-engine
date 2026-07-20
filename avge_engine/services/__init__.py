"""Shared engine services — graph access, doc resolution, validation."""
from avge_engine.services.engine import (
    get_graph,
    resolve_doc,
    set_active_doc,
    validate_input,
    load_design_guidelines,
    load_environment_guidelines,
    SMOOTHNESS_GUIDANCE,
)
from avge_engine.services.document_service import DocumentService

__all__ = [
    "DocumentService",
    "get_graph",
    "resolve_doc",
    "set_active_doc",
    "validate_input",
    "load_design_guidelines",
    "load_environment_guidelines",
    "SMOOTHNESS_GUIDANCE",
]
