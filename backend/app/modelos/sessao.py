from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.banco.conexao import BaseModelo


def data_atual():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SessaoRefresh(BaseModelo):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index(
            "ix_refresh_tokens_usuario_ativo",
            "empresa_id",
            "usuario_id",
            "revogado",
        ),
        Index("ix_refresh_tokens_expiracao", "expiracao"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    expiracao: Mapped[datetime] = mapped_column(DateTime)
    revogado: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=data_atual)
    usado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revogado_em: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
