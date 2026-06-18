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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco.conexao import BaseModelo


def data_atual():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Caixa(BaseModelo):
    __tablename__ = "cash_registers"
    __table_args__ = (
        UniqueConstraint("id", "empresa_id", name="uq_cash_registers_id_empresa"),
        UniqueConstraint(
            "id",
            "empresa_id",
            "usuario_id",
            name="uq_cash_registers_id_empresa_usuario",
        ),
        ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["users.id", "users.empresa_id"],
            name="fk_cash_registers_usuario_empresa",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('aberto', 'fechado')",
            name="ck_cash_registers_status",
        ),
        CheckConstraint(
            "valor_inicial >= 0",
            name="ck_cash_registers_valor_inicial",
        ),
        Index(
            "ix_cash_registers_empresa_usuario_status",
            "empresa_id",
            "usuario_id",
            "status",
        ),
        Index(
            "ix_cash_registers_empresa_abertura",
            "empresa_id",
            "data_abertura",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    usuario_id: Mapped[int] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(20), default="aberto")
    valor_inicial: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_dinheiro: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_pix: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_debito: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_credito: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_descontos: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_cancelamentos: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0,
    )
    total_sangrias: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0,
    )
    total_reforcos: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0,
    )
    total_devolucoes_dinheiro: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0,
    )
    valor_esperado: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    valor_real: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    diferenca: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    data_abertura: Mapped[datetime] = mapped_column(
        DateTime,
        default=data_atual,
    )
    data_fechamento: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    vendas = relationship("Venda", back_populates="caixa")
