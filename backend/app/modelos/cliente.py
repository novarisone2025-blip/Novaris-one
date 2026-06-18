from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco.conexao import BaseModelo


def data_atual():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Cliente(BaseModelo):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("id", "empresa_id", name="uq_customers_id_empresa"),
        UniqueConstraint(
            "empresa_id",
            "email",
            name="uq_customers_empresa_email",
        ),
        UniqueConstraint(
            "empresa_id",
            "documento",
            name="uq_customers_empresa_documento",
        ),
        ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["users.id", "users.empresa_id"],
            name="fk_customers_usuario_empresa",
            ondelete="RESTRICT",
        ),
        Index("ix_customers_empresa_nome", "empresa_id", "nome"),
        Index("ix_customers_empresa_documento", "empresa_id", "documento"),
        Index("ix_customers_empresa_telefone", "empresa_id", "telefone"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    usuario_id: Mapped[int] = mapped_column(index=True)
    nome: Mapped[str] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(180), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(30), nullable=True)
    documento: Mapped[str | None] = mapped_column(String(30), nullable=True)
    endereco: Mapped[str | None] = mapped_column(String(300), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    data_criacao: Mapped[datetime] = mapped_column(DateTime, default=data_atual)
    data_atualizacao: Mapped[datetime] = mapped_column(
        DateTime,
        default=data_atual,
        onupdate=data_atual,
    )

    vendas = relationship(
        "Venda",
        back_populates="cliente",
        overlaps="caixa,vendas",
    )
