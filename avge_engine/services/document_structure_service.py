"""Document structure operations: groups and layers."""
from __future__ import annotations

import math
from typing import Literal

from avge_engine.document.models import ElementNode
from avge_engine.services.base_element import BaseElementService


class DocumentStructureService(BaseElementService):
    """Application service for document groups and layer ordering."""

    def group_elements(
        self,
        group_name: str,
        element_ids: list[str],
        document_id: str | None = None,
        *,
        replace: bool = False,
    ) -> list[str]:
        doc_id = self.require_document_id(document_id)
        return self.documents.group_elements(doc_id, group_name, element_ids, replace=replace)

    def add_to_group(
        self,
        group_name: str,
        element_ids: list[str],
        document_id: str | None = None,
    ) -> list[str]:
        doc_id = self.require_document_id(document_id)
        return self.documents.add_to_group(doc_id, group_name, element_ids)

    def remove_from_group(
        self,
        group_name: str,
        element_ids: list[str],
        document_id: str | None = None,
    ) -> list[str]:
        doc_id = self.require_document_id(document_id)
        return self.documents.remove_from_group(doc_id, group_name, element_ids)

    def ungroup_elements(
        self,
        group_name: str | list[str],
        document_id: str | None = None,
    ) -> bool | list[str]:
        doc_id = self.require_document_id(document_id)
        return self.documents.ungroup_elements(doc_id, group_name)

    def get_group(self, group_name: str, document_id: str | None = None) -> list[dict]:
        doc_id = self.require_document_id(document_id)
        return self.documents.get_group(doc_id, group_name)

    def edit_group(
        self,
        *,
        action: Literal["create", "add", "remove", "delete"],
        group_name: str,
        element_ids: list[str] | None = None,
        document_id: str | None = None,
    ) -> dict:
        doc_id = self.require_document_id(document_id)
        if action == "delete":
            deleted = self.documents.ungroup_elements(doc_id, group_name)
            return {"group": group_name, "deleted": bool(deleted)}

        if not element_ids:
            raise ValueError("No element IDs provided")

        if action == "create":
            members = self.documents.group_elements(doc_id, group_name, element_ids, replace=True)
            return {"group": group_name, "members": members, "count": len(members)}
        if action == "add":
            members = self.documents.add_to_group(doc_id, group_name, element_ids)
            return {"group": group_name, "members": members, "count": len(members)}
        if action == "remove":
            removed = self.documents.remove_from_group(doc_id, group_name, element_ids)
            return {"group": group_name, "removed": removed, "count": len(removed)}
        raise ValueError(f"Unknown action '{action}'")

    def list_groups(self, *, document_id: str | None = None) -> list[dict[str, int]]:
        doc_id = self.require_document_id(document_id)
        return self.documents.list_groups(doc_id)

    def duplicate_group(
        self,
        *,
        group_name: str,
        document_id: str | None = None,
        new_prefix: str | None = None,
        dx: float = 0.0,
        dy: float = 0.0,
        scale: float = 1.0,
        sx: float | None = None,
        sy: float | None = None,
        rotate: float = 0.0,
        mirror_x: bool = False,
        mirror_y: bool = False,
    ) -> dict:
        doc_id = self.require_document_id(document_id)
        members = self.documents.get_group(doc_id, group_name)
        if not members:
            raise ValueError(f"Group '{group_name}' not found or empty")

        angle = math.radians(rotate)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        scale_x = sx if sx is not None else scale
        scale_y = sy if sy is not None else scale
        if mirror_x:
            scale_x = -abs(scale_x)
        if mirror_y:
            scale_y = -abs(scale_y)

        elements = self.elements_map(doc_id)
        new_ids: list[str] = []
        for member in members:
            rid = member["id"]
            original = elements.get(rid)
            if original is None:
                continue
            new_rid = f"{new_prefix or group_name + '_copy'}_{rid}"
            cx = sum(p[0] for p in original.outline) / len(original.outline)
            cy = sum(p[1] for p in original.outline) / len(original.outline)
            new_outline = []
            for x, y in original.outline:
                lx = (x - cx) * scale_x
                ly = (y - cy) * scale_y
                rx = lx * cos_a - ly * sin_a
                ry = lx * sin_a + ly * cos_a
                new_outline.append((rx + cx + dx, ry + cy + dy))

            self.add_element(
                doc_id,
                ElementNode(
                    id=new_rid,
                    layer=original.layer,
                    z_index=original.z_index,
                    clip_to=original.clip_to,
                    outline=new_outline,
                    constraints=original.constraints,
                    style=original.style,
                    transform=original.transform,
                    metadata=original.metadata.copy() if original.metadata else {},
                ),
            )
            new_ids.append(new_rid)

        if new_ids:
            self.documents.get(doc_id).group_elements(new_prefix or group_name + "_copy", new_ids, replace=True)
            self.commit(doc_id, action="duplicate_group", target=str(new_ids))
        return {"source_group": group_name, "new_ids": new_ids, "count": len(new_ids)}

    def list_layers(self, *, document_id: str | None = None) -> list[dict[str, int]]:
        doc_id = self.require_document_id(document_id)
        return self.documents.list_layers(doc_id)

    def shift_layer_z(self, *, layer: str, z_offset: int, document_id: str | None = None) -> int:
        doc_id = self.require_document_id(document_id)
        return self.documents.shift_layer_z(doc_id, layer, z_offset)
