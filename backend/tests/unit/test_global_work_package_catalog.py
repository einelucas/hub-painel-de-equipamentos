from __future__ import annotations

import importlib.util
from pathlib import Path


def test_migration_contains_all_37_canonical_work_packages() -> None:
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "0016_global_work_packages.py"
    )
    spec = importlib.util.spec_from_file_location("global_work_packages_migration", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    catalog = module.WORK_PACKAGE_CATALOG
    codes = [code for code, _ in catalog]
    assert len(catalog) == 37
    assert len(set(codes)) == 37
    assert all(code and description.strip() for code, description in catalog)
    assert {"IP001", "CIV004", "CAL008", "INT003", "EEI003"} <= set(codes)
