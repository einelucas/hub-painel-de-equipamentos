"""Normalizações explícitas e limitadas aos campos que pedem cada tipo."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Literal


class NormalizationError(ValueError):
    pass


_EMPTY_TEXT = {"", "null", "none", "n/a", "na", "-"}
_TRUE_TEXT = {"v", "true", "1", "sim", "yes", "y", "x", "checked", "✓", "✔"}
_FALSE_TEXT = {"false", "0", "nao", "não", "no", "n", "unchecked"}
_SPACE_RE = re.compile(r"\s+")


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = _SPACE_RE.sub(" ", str(value).strip())
    if text.casefold() in _EMPTY_TEXT:
        return None
    return text or None


def canonical_text(value: Any) -> str:
    text = clean_text(value) or ""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _SPACE_RE.sub(" ", without_accents.casefold()).strip()


def canonical_header(value: Any) -> str:
    text = canonical_text(value)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def normalized_name(value: Any) -> str:
    text = canonical_text(value)
    return re.sub(r"\s+", " ", text).strip()


def normalize_boolean(value: Any, *, empty: bool | None = None) -> bool | None:
    """Converte apenas quando o chamador sabe que o campo é booleano."""
    if value is None:
        return empty
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float) and not isinstance(value, bool):
        if value == 1:
            return True
        if value == 0:
            return False
    text = canonical_text(value)
    if text in _EMPTY_TEXT:
        return empty
    if text in _TRUE_TEXT:
        return True
    if text in _FALSE_TEXT:
        return False
    raise NormalizationError(f"valor booleano desconhecido: {value!r}")


def normalize_date(
    value: Any,
    *,
    excel_epoch: Literal["1900", "1904"] = "1900",
) -> date | None:
    """Normaliza uma data conhecida; nunca deve ser chamada para números genéricos."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, bool):
        raise NormalizationError(f"booleano não é data: {value!r}")

    numeric: float | None = None
    if isinstance(value, int | float | Decimal):
        numeric = float(value)
    else:
        text = clean_text(value)
        if text is None:
            return None
        if re.fullmatch(r"\d+(?:\.\d+)?", text):
            numeric = float(text)
        else:
            for pattern in ("%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(text, pattern).date()
                except ValueError:
                    continue
            raise NormalizationError(f"data inválida: {value!r}")

    if numeric is None or numeric < 1 or numeric > 2_958_465:
        raise NormalizationError(f"serial Excel fora do intervalo: {value!r}")
    epoch = date(1904, 1, 1) if excel_epoch == "1904" else date(1899, 12, 30)
    return epoch + timedelta(days=int(numeric))


def normalize_integer(value: Any, *, allow_negative: bool = True) -> int | None:
    if value is None:
        return None
    text = clean_text(value)
    if text is None:
        return None
    try:
        number = Decimal(text.replace(" ", ""))
    except InvalidOperation as exc:
        raise NormalizationError(f"inteiro inválido: {value!r}") from exc
    if number != number.to_integral_value():
        raise NormalizationError(f"inteiro inválido: {value!r}")
    result = int(number)
    if not allow_negative and result < 0:
        raise NormalizationError(f"inteiro negativo não permitido: {value!r}")
    return result


def normalize_decimal(value: Any) -> str | None:
    """Retorna string decimal JSON-safe sem assumir locale quando ambíguo."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, int | float) and not isinstance(value, bool):
        return format(Decimal(str(value)), "f")
    text = clean_text(value)
    if text is None:
        return None
    compact = re.sub(r"[^0-9,.-]", "", text)
    if "," in compact and "." in compact:
        compact = compact.replace(".", "").replace(",", ".")
    elif "," in compact:
        compact = compact.replace(",", ".")
    try:
        return format(Decimal(compact), "f")
    except InvalidOperation as exc:
        raise NormalizationError(f"decimal inválido: {value!r}") from exc


def normalize_multi_value(value: Any) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if canonical_text(text) in _EMPTY_TEXT:
        return []
    # Divide antes de `clean_text`, que intencionalmente colapsa whitespace.
    values = [clean_text(part) for part in re.split(r"[,;\r\n]+", text)]
    return [item for item in values if item is not None]


def normalize_external_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise NormalizationError("booleano não é external ID")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = clean_text(value)
    if text is None:
        return None
    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return text


def json_value(value: Any) -> Any:
    if isinstance(value, date | datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [json_value(item) for item in value]
    return value
