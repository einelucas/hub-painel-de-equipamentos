"""EAP corporativa (Ilha de Processo → Processo → Área) — regras puras, sem banco.

Identidade: o código da EAP NÃO inclui o prefixo da unidade. "01.A" é a
Caldeira em qualquer obra; o que o usuário vê ("2101.A", "2301.A", "2601.A")
é derivado de `unit.numeric_code + eap.code` e nunca persistido.

Parser de valores históricos do Monday: o código corporativo é lido pelo
SUFIXO do bloco numérico — os 2 últimos dígitos são o processo (01, 04,
08...), opcionalmente seguidos de ".X" (área/sub-EAP); o que vem antes é o
prefixo da unidade, com 2 ou mais dígitos (21, 23, 26 ou futuro 123) —
o mínimo de 2 evita ler números curtos soltos ("210 ...") como EAP.
O prefixo é opcional: "01.A Caldeira" e "08 Destilaria" são EAP sem unidade
(`unit_numeric_code=None`); o parser só representa o que está no valor bruto.
Valores que não seguem esse formato NÃO são forçados a virar EAP — voltam
como não estruturados, com diagnóstico.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum


class EapLevel(StrEnum):
    ISLAND = "ISLAND"
    PROCESS = "PROCESS"
    AREA = "AREA"


class EapIssueCode(StrEnum):
    # Detectados pelo parser puro.
    UNIT_PREFIX_MISMATCH = "UNIT_PREFIX_MISMATCH"
    UNSTRUCTURED_EAP_VALUE = "UNSTRUCTURED_EAP_VALUE"
    # Dependem do catálogo (ver `check_against_catalog`).
    UNKNOWN_EAP_CODE = "UNKNOWN_EAP_CODE"
    EAP_NAME_MISMATCH = "EAP_NAME_MISMATCH"


# Pai permitido por nível. ISLAND é raiz; PROCESS pode ficar na raiz enquanto
# as ilhas não forem catalogadas; AREA sempre pende de um PROCESS.
ALLOWED_PARENT_LEVELS: Mapping[EapLevel, frozenset[EapLevel | None]] = {
    EapLevel.ISLAND: frozenset({None}),
    EapLevel.PROCESS: frozenset({None, EapLevel.ISLAND}),
    EapLevel.AREA: frozenset({EapLevel.PROCESS}),
}

PROCESS_CODE_RE = re.compile(r"^\d{2}$")
AREA_CODE_RE = re.compile(r"^\d{2}\.[A-Z0-9]+$")
UNIT_NUMERIC_CODE_RE = re.compile(r"^\d+$")

# Níveis que um equipamento pode referenciar: a origem real tem tanto
# processo ("2108 Destilaria") quanto área ("2101.A Caldeira"). Ilha nunca.
EQUIPMENT_EAP_LEVELS: frozenset[EapLevel] = frozenset({EapLevel.PROCESS, EapLevel.AREA})

# "2101.A Caldeira" | "2304.A - Casa de Força" | "2108 Destilaria" | "12301.A Caldeira"
# | "01.A Caldeira" | "08 Destilaria"
# [<unit: 2+ dígitos>]<process: 2 dígitos>[.<sub>] — a divisão é feita pelo sufixo.
_REFERENCE_RE = re.compile(
    r"""^\s*
    (?P<unit>\d{2,}?)?
    (?P<process>\d{2})
    (?:\.(?P<sub>[A-Za-z0-9]+))?
    (?=\s|[-–—:]|$)
    \s*(?:[-–—:]\s*)?
    (?P<label>.*?)\s*$""",
    re.VERBOSE,
)


class EapRuleError(ValueError):
    pass


def assert_equipment_eap_level(level: EapLevel) -> None:
    """Equipamento referencia PROCESS ou AREA — nunca ISLAND."""
    if level not in EQUIPMENT_EAP_LEVELS:
        raise EapRuleError(f"equipamento não pode apontar para um nó {level.value} da EAP")


@dataclass(slots=True, frozen=True)
class EapIssue:
    code: EapIssueCode
    message: str
    expected: str | None = None
    found: str | None = None


@dataclass(slots=True, frozen=True)
class EapReference:
    """Interpretação de um valor histórico. `structured=False` = não é EAP."""

    raw: str
    structured: bool
    unit_numeric_code: str | None = None
    eap_code: str | None = None
    label: str | None = None
    issues: tuple[EapIssue, ...] = field(default_factory=tuple)

    def has_issue(self, code: EapIssueCode) -> bool:
        return any(issue.code == code for issue in self.issues)


def build_full_eap_code(unit_numeric_code: str, eap_code: str) -> str:
    """Código exibido ao usuário: prefixo da unidade + código corporativo."""
    unit = (unit_numeric_code or "").strip()
    code = (eap_code or "").strip()
    if not UNIT_NUMERIC_CODE_RE.fullmatch(unit):
        raise ValueError(f"código numérico de unidade inválido: {unit_numeric_code!r}")
    if not code:
        raise ValueError("código da EAP vazio")
    return f"{unit}{code}"


def parse_eap_reference(
    value: str | None, *, expected_unit_numeric_code: str | None = None
) -> EapReference | None:
    """Interpreta um valor do Monday sem consultar banco e sem criar nada.

    Nunca corrige o prefixo: divergência com a unidade esperada vira
    `UNIT_PREFIX_MISMATCH`, mantendo os valores encontrados. Sem prefixo no
    valor bruto, `unit_numeric_code` fica None (nunca copiado do esperado) e
    não há divergência a reportar — o código completo é derivado depois com
    `build_full_eap_code` e o código deve passar por `check_against_catalog`."""
    if value is None:
        return None
    raw = str(value)
    text = " ".join(raw.split())
    if not text:
        return None
    match = _REFERENCE_RE.match(text)
    if match is None:
        return EapReference(
            raw=raw,
            structured=False,
            label=text,
            issues=(
                EapIssue(
                    EapIssueCode.UNSTRUCTURED_EAP_VALUE,
                    "valor sem código EAP reconhecível; não é convertido em EAP",
                    found=text,
                ),
            ),
        )
    unit = match.group("unit")
    eap_code = match.group("process")
    if match.group("sub"):
        eap_code = f"{eap_code}.{match.group('sub').upper()}"
    issues: list[EapIssue] = []
    if (
        unit is not None
        and expected_unit_numeric_code is not None
        and unit != expected_unit_numeric_code.strip()
    ):
        issues.append(
            EapIssue(
                EapIssueCode.UNIT_PREFIX_MISMATCH,
                "prefixo de unidade diferente do esperado para este board",
                expected=expected_unit_numeric_code.strip(),
                found=unit,
            )
        )
    return EapReference(
        raw=raw,
        structured=True,
        unit_numeric_code=unit,
        eap_code=eap_code,
        label=match.group("label") or None,
        issues=tuple(issues),
    )


def _comparable(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    return " ".join("".join(c for c in decomposed if not unicodedata.combining(c)).casefold().split())


def check_against_catalog(reference: EapReference, catalog: Mapping[str, str]) -> tuple[EapIssue, ...]:
    """Confronta uma referência estruturada com um catálogo `{eap_code: nome}`
    fornecido pelo chamador (nenhum lookup de banco aqui)."""
    if not reference.structured or reference.eap_code is None:
        return ()
    official = catalog.get(reference.eap_code)
    if official is None:
        return (
            EapIssue(
                EapIssueCode.UNKNOWN_EAP_CODE,
                "código EAP não existe no catálogo corporativo",
                found=reference.eap_code,
            ),
        )
    if reference.label and _comparable(reference.label) != _comparable(official):
        return (
            EapIssue(
                EapIssueCode.EAP_NAME_MISMATCH,
                "nome no Monday difere do nome oficial do código EAP",
                expected=official,
                found=reference.label,
            ),
        )
    return ()


def validate_eap_node(
    *, code: str, level: EapLevel, parent_code: str | None, parent_level: EapLevel | None
) -> list[str]:
    """Regras estruturais de um nó. Lista vazia = válido.

    Formato fixo só para PROCESS ("01") e AREA ("01.A"). O formato das ILHAS
    será fechado após a Lista Geral de Documentos: por ora só não vazio, sem
    espaços e único. PROCESS pode ficar na raiz quando a ilha não é conhecida
    (nenhuma ilha fictícia é criada)."""
    errors: list[str] = []
    stripped = code.strip()
    if not stripped or stripped != code or " " in code:
        errors.append("código vazio ou com espaços")
    if level is EapLevel.PROCESS and not PROCESS_CODE_RE.fullmatch(code):
        errors.append("PROCESS deve ter 2 dígitos (ex.: 01) — nunca o prefixo da unidade")
    if level is EapLevel.AREA and not AREA_CODE_RE.fullmatch(code):
        errors.append("AREA deve seguir 01.A — nunca o prefixo da unidade")
    if parent_level not in ALLOWED_PARENT_LEVELS[level]:
        errors.append(
            f"{level.value} não pode ter pai do nível {parent_level.value if parent_level else 'raiz'}"
        )
    if level is EapLevel.AREA and parent_code is not None and not code.startswith(f"{parent_code}."):
        errors.append(f"AREA {code} não pertence ao PROCESS {parent_code}")
    return errors
