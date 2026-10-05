"""EAP corporativa (Ilha de Processo → Processo → Área) — regras puras, sem banco.

Identidade e exibição: o Hub usa SOMENTE `EapNode.code` ("03", "04.A",
"23.I"). Não existe composição "prefixo + EAP" — nem da unidade, nem da obra,
nem da fase (decisão P1.3.1; `ProjectContext.eap_prefix` é legado e não é lido).

Valores históricos do Monday carregam um prefixo CONTEXTUAL da planilha
("2303 - ...", "2104.A ...", "2323.I ..."). O parser lê o código corporativo
pelo SUFIXO do bloco numérico — os 2 últimos dígitos são o processo,
opcionalmente seguidos de ".X" (área/sub-EAP); o que vem antes (2+ dígitos) é
o prefixo contextual, descartado: "2104.A" e "2404.A" são a mesma EAP "04.A".
O mínimo de 2 dígitos no prefixo evita ler números curtos soltos ("210 ...").
Valores fora desse formato NÃO são forçados a virar EAP ("Diversos",
"Pré-Obra"). Nenhuma correspondência por nome é feita aqui.

Um valor pode citar várias EAPs ("2309 X / 2319 Y"): `extract_eap_codes`
devolve todas, sem escolher. O modelo atual tem um único `equipment.eap_node_id`;
um vínculo N:N é decisão de domínio futura.
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

# Níveis que um equipamento pode referenciar: a origem real tem tanto
# processo ("2108 Destilaria") quanto área ("2101.A Caldeira"). Ilha nunca.
EQUIPMENT_EAP_LEVELS: frozenset[EapLevel] = frozenset({EapLevel.PROCESS, EapLevel.AREA})

# "2301.A Caldeira" | "2304.A - Casa de Força" | "2408 Destilaria" | "12301.A Caldeira"
# | "01.A Caldeira" | "08 Destilaria" | "2300. Geral"
# [<prefixo contextual: 2+ dígitos>]<process: 2 dígitos>[.<sub> | .] — a divisão é feita pelo sufixo.
_REFERENCE_RE = re.compile(
    r"""^\s*
    (?P<prefix>\d{2,}?)?
    (?P<process>\d{2})
    (?:\.(?P<sub>[A-Za-z0-9]+)|\.(?=\s|$))?
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
    # Prefixo contextual encontrado e DESCARTADO ("23" em "2303 - ..."): só
    # evidência; nunca compõe nem distingue o código EAP.
    context_prefix: str | None = None
    eap_code: str | None = None
    label: str | None = None
    issues: tuple[EapIssue, ...] = field(default_factory=tuple)

    def has_issue(self, code: EapIssueCode) -> bool:
        return any(issue.code == code for issue in self.issues)


def parse_eap_reference(value: str | None) -> EapReference | None:
    """Interpreta UM valor do Monday sem consultar banco e sem criar nada.

    O prefixo contextual é removido (`context_prefix` guarda a evidência);
    `eap_code` é o código canônico a validar contra `EapNode.code`."""
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
    eap_code = match.group("process")
    if match.group("sub"):
        eap_code = f"{eap_code}.{match.group('sub').upper()}"
    return EapReference(
        raw=raw,
        structured=True,
        context_prefix=match.group("prefix"),
        eap_code=eap_code,
        label=match.group("label") or None,
    )


# Separadores de várias EAPs num mesmo valor ("2108 Destilaria / 2106 Fermentação").
# Só contam quando TODAS as partes são EAP estruturadas: "Outros/Diversos" ou
# "2304.A - Casa de Força/Subestação" não são listas de EAP.
_MULTI_SEPARATOR_RE = re.compile(r"\s*(?:/|;|\n)\s*")


def structured_parts(raw: str) -> list[str]:
    """Partes de um valor com várias EAPs; [] quando não é uma lista de EAPs."""
    parts = [part for part in _MULTI_SEPARATOR_RE.split(raw) if part.strip()]
    if len(parts) < 2:
        return []
    parsed = [parse_eap_reference(part) for part in parts]
    if all(ref is not None and ref.structured for ref in parsed):
        return parts
    return []


class EapLocationKind(StrEnum):
    NONE = "NONE"  # vazio ou sem código EAP ("Diversos", "Pré-Obra")
    SINGLE = "SINGLE"
    MULTIPLE = "MULTIPLE"


@dataclass(slots=True, frozen=True)
class EapLocation:
    """Todos os códigos EAP canônicos citados por um valor bruto de localização."""

    raw: str | None
    codes: tuple[str, ...] = ()

    @property
    def kind(self) -> EapLocationKind:
        if not self.codes:
            return EapLocationKind.NONE
        return EapLocationKind.SINGLE if len(self.codes) == 1 else EapLocationKind.MULTIPLE


def extract_eap_codes(value: str | None) -> EapLocation:
    """valor bruto → candidatos → prefixo contextual removido → códigos canônicos.

    Não valida contra o catálogo (isso exige `EapNode`) e nunca escolhe um
    candidato quando há mais de um. Códigos repetidos no mesmo valor contam uma vez."""
    if value is None or not str(value).strip():
        return EapLocation(raw=value)
    raw = str(value)
    parts = structured_parts(raw) or [raw]
    codes: list[str] = []
    for part in parts:
        reference = parse_eap_reference(part)
        if reference is not None and reference.eap_code and reference.eap_code not in codes:
            codes.append(reference.eap_code)
    return EapLocation(raw=raw, codes=tuple(codes))


def comparable_eap_name(name: str) -> str:
    """Forma de comparação de nomes da EAP: sem acentos, casefold e espaços
    normalizados. Só isso — nada de fuzzy, sinônimos ou remoção de palavras."""
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
    if reference.label and comparable_eap_name(reference.label) != comparable_eap_name(official):
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
        errors.append("PROCESS deve ter 2 dígitos (ex.: 01) — nunca o prefixo do projeto")
    if level is EapLevel.AREA and not AREA_CODE_RE.fullmatch(code):
        errors.append("AREA deve seguir 01.A — nunca o prefixo do projeto")
    if parent_level not in ALLOWED_PARENT_LEVELS[level]:
        errors.append(
            f"{level.value} não pode ter pai do nível {parent_level.value if parent_level else 'raiz'}"
        )
    if level is EapLevel.AREA and parent_code is not None and not code.startswith(f"{parent_code}."):
        errors.append(f"AREA {code} não pertence ao PROCESS {parent_code}")
    return errors
