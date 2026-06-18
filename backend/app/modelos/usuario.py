from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco.conexao import BaseModelo


def data_atual():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Usuario(BaseModelo):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("id", "empresa_id", name="uq_users_id_empresa"),
        CheckConstraint(
            "tipo_usuario IN ('admin', 'comum')",
            name="ck_users_tipo_usuario",
        ),
        Index("ix_users_empresa_ativo", "empresa_id", "ativo"),
        Index("ix_users_empresa_cargo", "empresa_id", "cargo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(
        String(180),
        unique=True,
        index=True,
    )
    senha_criptografada: Mapped[str] = mapped_column(String(255))
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    tipo_usuario: Mapped[str] = mapped_column(
        String(20),
        default="comum",
    )
    cargo: Mapped[str] = mapped_column(String(80), default="Usuario")
    permissoes: Mapped[str] = mapped_column(Text, default="[]")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    data_cadastro: Mapped[datetime] = mapped_column(
        DateTime,
        default=data_atual,
    )

    empresa = relationship("Empresa", back_populates="usuarios")
