"""Shared engine services — document access, doc resolution, validation."""
from avge_engine.services.engine import (
    get_document_operations,
    resolve_doc,
    set_active_doc,
    validate_input,
    load_design_guidelines,
    load_environment_guidelines,
    SMOOTHNESS_GUIDANCE,
)
from avge_engine.services.base import BaseService
from avge_engine.services.document_service import DocumentService
from avge_engine.services.creation_service import CreationService
from avge_engine.services.element_service import ElementService
from avge_engine.services.selector_service import SelectorService, select_element_ids, selector_from_legacy
from avge_engine.services.shadow_service import ShadowService
from avge_engine.services.style_service import StyleService

__all__ = [
    "DocumentService",
    "BaseService",
    "CreationService",
    "ElementService",
    "SelectorService",
    "ShadowService",
    "StyleService",
    "get_document_operations",
    "resolve_doc",
    "set_active_doc",
    "validate_input",
    "load_design_guidelines",
    "load_environment_guidelines",
    "select_element_ids",
    "selector_from_legacy",
    "SMOOTHNESS_GUIDANCE",
]
