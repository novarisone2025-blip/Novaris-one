from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco.conexao import BaseModelo


def data_atual():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Empresa(BaseModelo):
    __tablename__ = "companies"
    __table_args__ = (
        Index("ix_companies_nome", "nome"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    cnpj: Mapped[str | None] = mapped_column(String(20), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    data_criacao: Mapped[datetime] = mapped_column(
        DateTime,
        default=data_atual,
    )

    usuarios = relationship(
        "Usuario",
        back_populates="empresa",
        cascade="all, delete-orphan",
    )
