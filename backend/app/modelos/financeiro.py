from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.banco.conexao import BaseModelo


def data_atual():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class LancamentoFinanceiro(BaseModelo):
    __tablename__ = "financial_entries"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "empresa_id",
            name="uq_financial_entries_id_empresa",
        ),
        ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["users.id", "users.empresa_id"],
            name="fk_financial_entries_usuario_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["pedido_compra_id", "empresa_id"],
            ["purchase_orders.id", "purchase_orders.empresa_id"],
            name="fk_financial_entries_pedido_empresa",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "tipo IN ('entrada', 'saida')",
            name="ck_financial_entries_tipo",
        ),
        CheckConstraint("valor > 0", name="ck_financial_entries_valor"),
        Index(
            "ix_financial_entries_empresa_data",
            "empresa_id",
            "data_lancamento",
        ),
        Index(
            "ix_financial_entries_empresa_tipo_data",
            "empresa_id",
            "tipo",
            "data_lancamento",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    usuario_id: Mapped[int] = mapped_column()
    pedido_compra_id: Mapped[int | None] = mapped_column(
        nullable=True,
        index=True,
    )
    tipo: Mapped[str] = mapped_column(String(20))
    categoria: Mapped[str] = mapped_column(String(80))
    descricao: Mapped[str] = mapped_column(String(220))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    data_lancamento: Mapped[datetime] = mapped_column(
        DateTime,
        default=data_atual,
        index=True,
    )
