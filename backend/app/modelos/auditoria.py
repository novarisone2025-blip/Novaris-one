from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.banco.conexao import BaseModelo


def data_atual():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class LogAuditoria(BaseModelo):
    __tablename__ = "audit_logs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["users.id", "users.empresa_id"],
            name="fk_audit_logs_usuario_empresa",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_audit_logs_empresa_data",
            "empresa_id",
            "data_acao",
        ),
        Index(
            "ix_audit_logs_empresa_usuario_data",
            "empresa_id",
            "usuario_id",
            "data_acao",
        ),
        Index(
            "ix_audit_logs_empresa_acao_data",
            "empresa_id",
            "acao",
            "data_acao",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    usuario_id: Mapped[int] = mapped_column(index=True)
    acao: Mapped[str] = mapped_column(String(80))
    entidade: Mapped[str] = mapped_column(String(80))
    entidade_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detalhes: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_acao: Mapped[datetime] = mapped_column(DateTime, default=data_atual)
