from __future__ import annotations

from sqlalchemy import ColumnElement, select

from app.models.equipment import EapNode, Equipment


def equipment_in_eap_subtree(eap_node_id: str) -> ColumnElement[bool]:
    """Equipamento localizado no nó EAP informado ou em qualquer descendente.

    Filtrar por um Processo também traz os equipamentos das Áreas abaixo dele.
    Usa somente `eap_node_id` (fonte canônica), nunca a `area_id` legada.
    """
    subtree = select(EapNode.id).where(EapNode.id == eap_node_id).cte("eap_subtree", recursive=True)
    subtree = subtree.union_all(select(EapNode.id).where(EapNode.parent_id == subtree.c.id))
    return Equipment.eap_node_id.in_(select(subtree.c.id))
