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
from avge_engine.services.selector_service import SelectorService, select_region_ids, selector_from_legacy
from avge_engine.services.style_service import StyleService

__all__ = [
    "DocumentService",
    "SelectorService",
    "StyleService",
    "get_graph",
    "resolve_doc",
    "set_active_doc",
    "validate_input",
    "load_design_guidelines",
    "load_environment_guidelines",
    "select_region_ids",
    "selector_from_legacy",
    "SMOOTHNESS_GUIDANCE",
]
