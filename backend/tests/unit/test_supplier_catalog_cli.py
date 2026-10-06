from __future__ import annotations

from argparse import Namespace

import pytest

from app.modules.supplier_catalog.cli import _cmd_seed, build_parser


@pytest.mark.parametrize(
    "arguments",
    [
        ["seed", "--apply", "--expect-database", "neondb_test"],
        ["seed", "--apply", "--confirm"],
    ],
)
def test_apply_requires_confirm_and_expected_database(arguments: list[str]) -> None:
    parsed = build_parser().parse_args(arguments)
    with pytest.raises(SystemExit, match="--apply exige --confirm e --expect-database"):
        _cmd_seed(parsed)


def test_parser_accepts_guarded_apply() -> None:
    parsed: Namespace = build_parser().parse_args(
        ["seed", "--apply", "--sync", "--confirm", "--expect-database", "neondb_test"]
    )
    assert parsed.apply is True
    assert parsed.sync is True
    assert parsed.confirm is True
    assert parsed.expect_database == "neondb_test"


def test_apply_is_blocked_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:secret@db.example/prod")
    get_settings.cache_clear()
    parsed = build_parser().parse_args(
        ["seed", "--apply", "--confirm", "--expect-database", "prod"]
    )
    try:
        with pytest.raises(SystemExit, match="não é 'test' nem 'development'"):
            _cmd_seed(parsed)
    finally:
        get_settings.cache_clear()
