"""Vínculo entre usuário e unidade.

O perfil (`role`) define **o que** o usuário pode fazer; este vínculo define
**onde**. ADMIN não depende da tabela: enxerga todas as unidades ativas.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.common import Timestamp3, utcnow, uuid_pk
from app.models.equipment import Unit
from app.models.user import User


class UserUnitAccess(Base):
    __tablename__ = "user_unit_access"

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("User.id", ondelete="CASCADE"), nullable=False
    )
    unit_id: Mapped[str] = mapped_column(
        ForeignKey("unit.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(Timestamp3, nullable=False, default=utcnow)

    user: Mapped[User] = relationship("User")
    unit: Mapped[Unit] = relationship("Unit")

    __table_args__ = (
        Index("user_unit_access_user_unit_key", "user_id", "unit_id", unique=True),
        Index("user_unit_access_user_id_idx", "user_id"),
    )
