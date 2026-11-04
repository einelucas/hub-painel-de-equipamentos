"""Eventos persistentes de sincronização e limpeza assíncrona de arquivos.

Os eventos são gravados na mesma transação da alteração de domínio. Assim,
uma conexão SSE só os enxerga depois do commit e qualquer rollback também
remove o evento. O registro não possui FK para a entidade alterada de
propósito: o evento de exclusão precisa sobreviver à remoção da obra.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk


class SyncEvent(Base):
    __tablename__ = "sync_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    unit_id: Mapped[str] = mapped_column(String, nullable=False)
    project_context_id: Mapped[str | None] = mapped_column(String, nullable=True)
    equipment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("User.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)

    __table_args__ = (
        Index("sync_event_unit_id_id_idx", "unit_id", "id"),
        Index("sync_event_project_context_id_id_idx", "project_context_id", "id"),
        Index("sync_event_equipment_id_id_idx", "equipment_id", "id"),
    )


class ContractFileCleanup(Base):
    """Outbox durável para apagar objetos depois do commit da exclusão.

    Storage externo não participa da transação PostgreSQL. Manter a chave
    nesta fila evita perder a referência caso o S3 esteja indisponível no
    momento em que a obra é removida.
    """

    __tablename__ = "contract_file_cleanup"

    id: Mapped[str] = uuid_pk()
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp3, nullable=False, default=utcnow, onupdate=utcnow
    )

