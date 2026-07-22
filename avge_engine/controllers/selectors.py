"""Backward-compatible selector imports for older controller code."""
from avge_engine.services.selector_service import SelectorService, select_element_ids, selector_from_legacy

__all__ = ["SelectorService", "select_element_ids", "selector_from_legacy"]
