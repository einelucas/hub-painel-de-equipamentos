"""Extração do catálogo EAP a partir da Árvore de Localização oficial — pura, sem I/O.

Usada só em desenvolvimento (`python -m app.modules.eap_catalog extract`): o
aplicativo nunca abre o XLSX em runtime, só o JSON versionado gerado aqui.

Leitura da Árvore (coluna A = ÁREA, coluna B = SETOR):

- `X<letra> <nome>` (sem SETOR) abre um bloco de ILHA. `X <nome>` sem letra é
  uma ilha sem código — nenhum código é inventado para ela.
- `X<NN>` é um PROCESS e `X<NN>.<sub>` uma AREA; o `X` é o marcador do prefixo
  do projeto e NÃO faz parte da identidade (`X01.A` → `01.A`).
- Qualquer outra linha (ex.: "Materiais", "Geral | Controle de listas…") é
  atribuição de responsabilidade, não nó da árvore.

Decisões de domínio aprovadas (`app/data/eap_catalog_resolutions.json`) entram
como `EapResolution`: cada uma vale para UM código e só se a Árvore trouxer
exatamente os nomes registrados nela — se a fonte mudar, a extração falha em
vez de aplicar a decisão antiga em silêncio. Os nomes da fonte ficam no nó
(`source_names`).

Nada é decidido por escolha arbitrária: quando um nó não pode ser representado
de forma inequívoca (código repetido com descrições diferentes, marcador
malformado, posição que contradiz o código, ilha sem código), ele vai para
`review_required` com as alternativas encontradas — e seus descendentes
também, porque não podem ser carregados sem o pai.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from app.domain.eap import EapLevel, validate_eap_node

ISLAND_HEADER_RE = re.compile(r"^X(?P<letter>[A-Z])?\s+(?P<name>\S.*)$")
NODE_RE = re.compile(r"^(?P<marker>X+)(?P<process>\d{2})(?:\.(?P<sub>[A-Z0-9]+))?$")
NAME_MAX_LENGTH = 160

# Motivos de revisão (valores estáveis, gravados no JSON).
ISLAND_CODE_MISSING = "ISLAND_CODE_MISSING"
DUPLICATE_CODE = "DUPLICATE_CODE_DIFFERENT_NAMES"
MALFORMED_MARKER = "MALFORMED_PREFIX_MARKER"
POSITION_MISMATCH = "POSITION_CONTRADICTS_CODE"
PARENT_NOT_FOUND = "PARENT_NOT_FOUND"
PARENT_REVIEW_REQUIRED = "PARENT_REVIEW_REQUIRED"
INVALID_NODE = "INVALID_NODE"

_LEVEL_ORDER = {EapLevel.ISLAND: 0, EapLevel.PROCESS: 1, EapLevel.AREA: 2}


@dataclass(slots=True, frozen=True)
class TreeRow:
    number: int
    area: object
    sector: object


@dataclass(slots=True, frozen=True)
class _Occurrence:
    row: int
    name: str
    marker: str
    island_key: str | None  # letra da ilha, ou "row:<n>" para ilha sem código
    block_process: str | None  # último PROCESS visto antes desta linha


class EapResolutionError(ValueError):
    pass


@dataclass(slots=True, frozen=True)
class EapResolution:
    """Decisão de domínio aprovada para um código que a Árvore traz de forma ambígua."""

    code: str
    level: EapLevel
    canonical_name: str
    parent_code: str | None
    source_names: tuple[str, ...]
    decision: str


@dataclass(slots=True)
class ExtractedNode:
    level: EapLevel
    code: str
    name: str
    parent_code: str | None
    source_rows: list[int]
    resolution: EapResolution | None = None

    def as_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "level": self.level.value,
            "code": self.code,
            "name": self.name,
            "parent_code": self.parent_code,
            "source_rows": self.source_rows,
        }
        if self.resolution is not None:
            data["source_names"] = list(self.resolution.source_names)
            data["resolution"] = self.resolution.decision
        return data


@dataclass(slots=True)
class ReviewItem:
    level: EapLevel
    code: str | None
    names_found: list[str]
    reason: str
    detail: str
    source_rows: list[int]
    alternatives: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "status": "EAP_REVIEW_REQUIRED",
            "level": self.level.value,
            "code": self.code,
            "names_found": self.names_found,
            "reason": self.reason,
            "detail": self.detail,
            "source_rows": self.source_rows,
            "alternatives": self.alternatives,
        }


@dataclass(slots=True)
class ExtractedTree:
    nodes: list[ExtractedNode] = field(default_factory=list)
    review_required: list[ReviewItem] = field(default_factory=list)
    eap_rows: int = 0
    island_rows: int = 0
    non_eap_rows: list[int] = field(default_factory=list)


def clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def extract_tree(
    rows: Iterable[TreeRow], resolutions: Mapping[str, EapResolution] | None = None
) -> ExtractedTree:
    resolutions = resolutions or {}
    result = ExtractedTree()
    islands: dict[str, tuple[str | None, str, int]] = {}  # chave -> (letra, nome, linha)
    occurrences: dict[str, list[_Occurrence]] = {}
    current_island: str | None = None
    current_process: str | None = None

    for row in rows:
        area = clean_text(row.area)
        sector = clean_text(row.sector)
        if area is None:
            continue
        island_match = ISLAND_HEADER_RE.fullmatch(area) if sector is None else None
        node_match = NODE_RE.fullmatch(area) if sector is not None else None
        if island_match is not None:
            letter = island_match.group("letter")
            current_island = letter if letter is not None else f"row:{row.number}"
            current_process = None
            islands[current_island] = (letter, island_match.group("name"), row.number)
            result.island_rows += 1
        elif node_match is not None:
            code = node_match.group("process")
            if node_match.group("sub"):
                code = f"{code}.{node_match.group('sub')}"
            else:
                current_process = code
            occurrences.setdefault(code, []).append(
                _Occurrence(
                    row.number, str(sector), node_match.group("marker"), current_island, current_process
                )
            )
            result.eap_rows += 1
        else:
            result.non_eap_rows.append(row.number)

    candidates: dict[str, ExtractedNode] = {}
    parent_keys: dict[str, str | None] = {}
    reviews: dict[str, ReviewItem] = {}

    for key, (letter, name, row_number) in islands.items():
        if letter is None:
            reviews[key] = ReviewItem(
                EapLevel.ISLAND,
                None,
                [name],
                ISLAND_CODE_MISSING,
                "Cabeçalho de ilha sem letra na Árvore: não há código oficial para o nó.",
                [row_number],
                ["Definir o código oficial desta ilha (a Árvore não traz letra para o bloco)."],
            )
        else:
            candidates[key] = ExtractedNode(EapLevel.ISLAND, letter, name, None, [row_number])
            parent_keys[key] = None

    for code, found in occurrences.items():
        level = EapLevel.AREA if "." in code else EapLevel.PROCESS
        rows_found = [item.row for item in found]
        names = list(dict.fromkeys(item.name for item in found))
        first = found[0]
        island_label = islands[first.island_key][0] if first.island_key in islands else None
        resolution = resolutions.get(code)
        if resolution is not None:
            if resolution.level is not level or tuple(names) != resolution.source_names:
                raise EapResolutionError(
                    f"Resolução de {code} não confere com a Árvore: esperado {list(resolution.source_names)} "
                    f"({resolution.level.value}), encontrado {names} ({level.value})."
                )
            if any(item.marker != "X" for item in found):
                raise EapResolutionError(f"Resolução de {code}: marcador de prefixo malformado na Árvore.")
            candidates[code] = ExtractedNode(
                level, code, resolution.canonical_name, resolution.parent_code, rows_found, resolution
            )
            parent_keys[code] = resolution.parent_code
            continue
        if len(names) > 1:
            reviews[code] = ReviewItem(
                level,
                code,
                names,
                DUPLICATE_CODE,
                f"O código aparece em {len(found)} linhas com descrições diferentes.",
                rows_found,
                [f"'{item.name}' (linha {item.row})" for item in found],
            )
            continue
        if any(item.marker != "X" for item in found):
            reviews[code] = ReviewItem(
                level,
                code,
                names,
                MALFORMED_MARKER,
                f"Marcador de prefixo '{first.marker}' em vez de 'X' ('{first.marker}{code}').",
                rows_found,
                [
                    f"'{code}' lido com o marcador corrigido para 'X'",
                    f"posição na Árvore: bloco da ilha {island_label or '(sem código)'}",
                ],
            )
            continue
        if level is EapLevel.PROCESS:
            parent_key = first.island_key
            parent_code = island_label
        else:
            parent_key = parent_code = code.split(".", 1)[0]
            if first.block_process != parent_code:
                sub = code.split(".", 1)[1]
                reviews[code] = ReviewItem(
                    level,
                    code,
                    names,
                    POSITION_MISMATCH,
                    f"O código indica o PROCESS {parent_code}, mas a linha está no bloco do "
                    f"PROCESS {first.block_process}.",
                    rows_found,
                    [
                        f"pai {parent_code} (pelo código)",
                        f"pai {first.block_process} (pela posição; "
                        f"o código seria {first.block_process}.{sub})",
                    ],
                )
                continue
        candidates[code] = ExtractedNode(level, code, first.name, parent_code, rows_found)
        parent_keys[code] = parent_key

    unused = sorted(set(resolutions) - set(occurrences))
    if unused:
        raise EapResolutionError(f"Resoluções sem código correspondente na Árvore: {unused}")

    # Um nó só é carregável se o pai também for (propaga até estabilizar).
    changed = True
    while changed:
        changed = False
        for key, node in list(candidates.items()):
            parent_key = parent_keys[key]
            if node.level is EapLevel.ISLAND or (parent_key is None and node.level is EapLevel.PROCESS):
                continue
            if parent_key in reviews:
                parent = reviews[parent_key]
                parent_label = parent.code or f"ilha '{parent.names_found[0]}'"
                reviews[key] = ReviewItem(
                    node.level,
                    node.code,
                    [node.name],
                    PARENT_REVIEW_REQUIRED,
                    f"O pai ({parent_label}) está em revisão; o nó não pode ser carregado sem ele.",
                    node.source_rows,
                    [f"Carregar após resolver {parent_label}"],
                )
            elif parent_key not in candidates:
                reviews[key] = ReviewItem(
                    node.level,
                    node.code,
                    [node.name],
                    PARENT_NOT_FOUND,
                    f"O pai {parent_key} não existe na Árvore.",
                    node.source_rows,
                    [f"Cadastrar {parent_key} na Árvore"],
                )
            else:
                continue
            del candidates[key]
            changed = True

    for key, node in list(candidates.items()):
        parent_level = None
        if node.parent_code is not None:
            parent_level = EapLevel.ISLAND if node.level is EapLevel.PROCESS else EapLevel.PROCESS
        errors = validate_eap_node(
            code=node.code, level=node.level, parent_code=node.parent_code, parent_level=parent_level
        )
        if len(node.name) > NAME_MAX_LENGTH:
            errors.append(f"nome com mais de {NAME_MAX_LENGTH} caracteres")
        if errors:
            reviews[key] = ReviewItem(
                node.level, node.code, [node.name], INVALID_NODE, "; ".join(errors), node.source_rows, []
            )
            del candidates[key]

    result.nodes = sorted(candidates.values(), key=lambda n: (_LEVEL_ORDER[n.level], n.code))
    result.review_required = sorted(
        reviews.values(), key=lambda r: (_LEVEL_ORDER[r.level], r.code or "", r.source_rows[0])
    )
    return result
