"""Fundação auditável para importar exportações XLSX do Monday."""

from app.modules.monday_import.parser import parse_monday_xlsx

__all__ = ["parse_monday_xlsx"]
