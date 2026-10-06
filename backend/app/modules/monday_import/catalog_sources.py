"""Fontes padrão de evidência de catálogo para o `plan` (arquivos locais).

- catálogo oficial: `eap_catalog.json` gerado do catálogo consolidado
  (`EAP_CATALOG_PATH`; ausente = sem essa fonte);
- LGE: `MONDAY_IMPORT_LGE_PATH` (ausente/ilegível = sem essa fonte, com log);
- manual: `catalogEvidence` do mapping.

Nenhum desses arquivos é versionado.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.modules.monday_import.catalog_evidence import CatalogEvidence, LgeReadError, build_catalog_evidence
from app.modules.monday_import.mapping_file import ValidatedMapping

logger = logging.getLogger(__name__)


def _official_document() -> Mapping[str, Any] | None:
    from app.modules.eap_catalog.catalog import CATALOG_PATH

    path = Path(CATALOG_PATH)
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("catálogo EAP oficial ilegível; plan segue sem essa fonte")
        return None
    return document if isinstance(document, Mapping) else None


def default_catalog_evidence(
    normalized_records: Iterable[Mapping[str, Any]], mapping: ValidatedMapping
) -> CatalogEvidence:
    lge_path = get_settings().monday_import_lge_path
    if lge_path and not Path(lge_path).is_file():
        logger.warning("MONDAY_IMPORT_LGE_PATH não encontrado; plan segue sem a LGE")
        lge_path = None
    try:
        return build_catalog_evidence(
            normalized_records,
            manual=mapping.catalog_evidence,
            official_document=_official_document(),
            lge_path=lge_path,
        )
    except LgeReadError as exc:
        logger.warning("LGE ilegível (%s); plan segue sem a LGE", exc)
        return build_catalog_evidence(
            normalized_records, manual=mapping.catalog_evidence, official_document=_official_document()
        )
