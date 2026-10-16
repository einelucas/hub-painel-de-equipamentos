from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import pytest

from app.core.storage import (
    LocalContractFileStorage,
    S3ContractFileStorage,
    StorageObjectNotFoundError,
)


class NoSuchKey(Exception):
    pass


class FakeS3:
    exceptions = SimpleNamespace(NoSuchKey=NoSuchKey)

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:  # noqa: N803
        self.objects[(Bucket, Key)] = Body

    def get_object(self, *, Bucket: str, Key: str) -> dict:  # noqa: N803
        try:
            return {"Body": BytesIO(self.objects[(Bucket, Key)])}
        except KeyError as exc:
            raise NoSuchKey from exc

    def delete_object(self, *, Bucket: str, Key: str) -> None:  # noqa: N803
        self.objects.pop((Bucket, Key), None)


async def test_local_storage_rejects_path_traversal(tmp_path) -> None:  # noqa: ANN001
    storage = LocalContractFileStorage(str(tmp_path))
    with pytest.raises(ValueError, match="inválida"):
        await storage.save("../fora", b"segredo")


async def test_s3_storage_round_trip_with_prefix() -> None:
    client = FakeS3()
    storage = S3ContractFileStorage(bucket="contracts", prefix="production", client=client)

    await storage.save("contracts/c1/object", b"pdf")
    assert await storage.load("contracts/c1/object") == b"pdf"
    assert ("contracts", "production/contracts/c1/object") in client.objects

    await storage.delete("contracts/c1/object")
    with pytest.raises(StorageObjectNotFoundError):
        await storage.load("contracts/c1/object")
