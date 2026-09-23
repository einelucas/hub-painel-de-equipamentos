"""Abstração de object storage para arquivos de contrato (Etapa 7A, seção I).

O projeto não tinha nenhuma estratégia de storage antes desta etapa. Em vez
de acoplar o domínio a filesystem ou inventar credenciais de nuvem, isto
define uma interface mínima (`ContractFileStorage`) com uma implementação
local segura para DEV/teste. Produção com `storage_provider="local"` é
bloqueada explicitamente — o provider real (S3/Azure Blob/etc.) é uma
pendência de infraestrutura registrada em
`docs/validation/etapa-07-operational-business-rules.md`, não decidida
aqui.

Metadados do arquivo (nome, tipo, tamanho, quem/quando) ficam no Postgres
(`Contract.file_*`); só os bytes passam por aqui.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


class StorageNotConfiguredError(Exception):
    """Produção sem um provider de storage real configurado."""


class ContractFileStorage(Protocol):
    async def save(self, key: str, content: bytes) -> None: ...

    async def load(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...


class LocalContractFileStorage:
    """Grava no filesystem do processo. Correto para DEV/teste; nunca usar
    em produção (efêmero em qualquer ambiente com deploy imutável/múltiplas
    instâncias)."""

    def __init__(self, base_dir: str) -> None:
        self._base_dir = Path(base_dir)

    def _path(self, key: str) -> Path:
        # `key` é sempre gerado pelo serviço (uuid do contrato + sufixo),
        # nunca vem direto de input do usuário — sem risco de path traversal.
        return self._base_dir / key

    async def save(self, key: str, content: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    async def load(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()


def get_contract_file_storage() -> ContractFileStorage:
    settings = get_settings()
    if settings.is_production:
        # Nenhum provider real de produção foi definido ainda — bloqueia em
        # vez de gravar arquivo de contrato real num filesystem efêmero.
        raise StorageNotConfiguredError(
            "STORAGE_PROVIDER='local' não é seguro em produção. Configure um "
            "provider real (S3/Azure Blob/etc.) antes de habilitar upload de "
            "contrato em produção — pendência de infraestrutura registrada "
            "em docs/validation/etapa-07-operational-business-rules.md."
        )
    return LocalContractFileStorage(settings.storage_local_dir)
