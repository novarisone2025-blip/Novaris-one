from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco.conexao import BaseModelo


def data_atual():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Fornecedor(BaseModelo):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "nome",
            name="uq_fornecedor_empresa_nome",
        ),
        UniqueConstraint("id", "empresa_id", name="uq_suppliers_id_empresa"),
        Index("ix_suppliers_empresa_nome", "empresa_id", "nome"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    nome: Mapped[str] = mapped_column(String(180))
    cnpj: Mapped[str | None] = mapped_column(String(20), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    contato: Mapped[str | None] = mapped_column(String(120), nullable=True)
    data_criacao: Mapped[datetime] = mapped_column(DateTime, default=data_atual)

    produtos = relationship("Produto", back_populates="fornecedor")
