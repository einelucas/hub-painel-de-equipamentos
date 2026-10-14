"""`stage_import` repassa ao parser o nome derivado da fonte (Path/stream), não o padrão."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

from app.modules.monday_import import service as service_module


class _Stop(Exception):
    pass


class _Session:
    async def scalar(self, _statement: Any) -> str:
        return "ctx"


async def _captured_source_name(monkeypatch: pytest.MonkeyPatch, source: Any, **kwargs: Any) -> str | None:
    captured: dict[str, Any] = {}

    async def no_batch(*_: Any) -> None:
        return None

    def fake_parse(_data: bytes, *, source_name: str | None, profile: Any) -> Any:
        captured["source_name"] = source_name
        raise _Stop

    monkeypatch.setattr(service_module, "_find_batch", no_batch)
    monkeypatch.setattr(service_module, "parse_monday_xlsx", fake_parse)
    with pytest.raises(_Stop):
        await service_module.stage_import(
            _Session(),  # type: ignore[arg-type]
            project_context_id="ctx",
            source=source,
            **kwargs,
        )
    return captured["source_name"]


async def test_path_source_keeps_its_file_name(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "Equipamentos Monday.xlsx"
    path.write_bytes(b"x")
    assert await _captured_source_name(monkeypatch, path) == "Equipamentos Monday.xlsx"


async def test_stream_source_uses_its_name_and_explicit_name_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = io.BytesIO(b"x")
    stream.name = "/tmp/board.xlsx"  # type: ignore[attr-defined]
    assert await _captured_source_name(monkeypatch, stream) == "board.xlsx"
    assert await _captured_source_name(monkeypatch, b"x", source_name="a.xlsx") == "a.xlsx"
    assert await _captured_source_name(monkeypatch, b"x") == "upload.xlsx"
