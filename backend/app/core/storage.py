"""Object storage dos arquivos de contrato."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Protocol

from app.core.config import get_settings


class StorageNotConfiguredError(Exception):
    """Provider ausente ou incompleto."""


class StorageObjectNotFoundError(Exception):
    """Objeto referenciado no banco não existe mais no storage."""


class ContractFileStorage(Protocol):
    async def save(self, key: str, content: bytes) -> None: ...

    async def load(self, key: str) -> bytes: ...

    async def delete(self, key: str) -> None: ...


class LocalContractFileStorage:
    """Filesystem persistente apenas para desenvolvimento e testes."""

    def __init__(self, base_dir: str) -> None:
        self._base_dir = Path(base_dir).resolve()

    def _path(self, key: str) -> Path:
        path = (self._base_dir / key).resolve()
        if not path.is_relative_to(self._base_dir):
            raise ValueError("Chave de storage inválida.")
        return path

    async def save(self, key: str, content: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    async def load(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as exc:
            raise StorageObjectNotFoundError(key) from exc

    async def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()


class S3ContractFileStorage:
    """Implementação S3 compatível (AWS, Railway Bucket, R2, MinIO etc.)."""

    def __init__(self, *, bucket: str, prefix: str = "", client: Any) -> None:
        self._bucket = bucket
        self._prefix = prefix.strip("/")
        self._client = client

    def _key(self, key: str) -> str:
        return f"{self._prefix}/{key}" if self._prefix else key

    async def save(self, key: str, content: bytes) -> None:
        await asyncio.to_thread(
            self._client.put_object, Bucket=self._bucket, Key=self._key(key), Body=content
        )

    async def load(self, key: str) -> bytes:
        try:
            response = await asyncio.to_thread(
                self._client.get_object, Bucket=self._bucket, Key=self._key(key)
            )
            return await asyncio.to_thread(response["Body"].read)
        except self._client.exceptions.NoSuchKey as exc:
            raise StorageObjectNotFoundError(key) from exc

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object, Bucket=self._bucket, Key=self._key(key)
        )


def get_contract_file_storage() -> ContractFileStorage:
    settings = get_settings()
    if settings.storage_provider == "s3":
        if not settings.storage_s3_bucket:
            raise StorageNotConfiguredError("STORAGE_S3_BUCKET é obrigatório para STORAGE_PROVIDER=s3.")
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=settings.storage_s3_endpoint_url,
            region_name=settings.storage_s3_region,
            aws_access_key_id=settings.storage_s3_access_key_id,
            aws_secret_access_key=settings.storage_s3_secret_access_key,
        )
        return S3ContractFileStorage(
            bucket=settings.storage_s3_bucket,
            prefix=settings.storage_s3_prefix,
            client=client,
        )
    if settings.is_production:
        raise StorageNotConfiguredError(
            "STORAGE_PROVIDER=local não é seguro em produção; configure STORAGE_PROVIDER=s3."
        )
    return LocalContractFileStorage(settings.storage_local_dir)
