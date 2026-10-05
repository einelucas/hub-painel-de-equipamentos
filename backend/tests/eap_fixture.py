"""Caminhos da fixture EAP sintética (`tests/fixtures/eap/`).

A EAP real é privada e não é versionada; nenhum teste depende dela.
"""

from __future__ import annotations

from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "eap"
CATALOG_PATH = FIXTURE_DIR / "eap_catalog.json"
RESOLUTIONS_PATH = FIXTURE_DIR / "eap_catalog_resolutions.json"
ALIASES_PATH = FIXTURE_DIR / "eap_aliases.json"
