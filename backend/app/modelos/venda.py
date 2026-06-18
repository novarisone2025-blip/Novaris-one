from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco.conexao import BaseModelo


def data_atual():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Venda(BaseModelo):
    __tablename__ = "sales"
    __table_args__ = (
        UniqueConstraint("id", "empresa_id", name="uq_sales_id_empresa"),
        ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["users.id", "users.empresa_id"],
            name="fk_sales_usuario_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["caixa_id", "empresa_id", "usuario_id"],
            [
                "cash_registers.id",
                "cash_registers.empresa_id",
                "cash_registers.usuario_id",
            ],
            name="fk_sales_caixa_usuario_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["cliente_id", "empresa_id"],
            ["customers.id", "customers.empresa_id"],
            name="fk_sales_cliente_empresa",
            ondelete="RESTRICT",
        ),
        CheckConstraint("subtotal >= 0", name="ck_sales_subtotal"),
        CheckConstraint("desconto >= 0", name="ck_sales_desconto"),
        CheckConstraint(
            "valor_total >= 0 AND valor_total = subtotal - desconto",
            name="ck_sales_valor_total",
        ),
        CheckConstraint(
            "forma_pagamento IN ('dinheiro', 'pix', 'debito', 'credito')",
            name="ck_sales_forma_pagamento",
        ),
        CheckConstraint(
            "status IN ('aguardando_pagamento', 'pago', 'cancelado')",
            name="ck_sales_status",
        ),
        CheckConstraint(
            "(forma_pagamento = 'dinheiro' "
            "AND valor_recebido IS NOT NULL "
            "AND troco_entregue IS NOT NULL "
            "AND valor_recebido >= valor_total "
            "AND troco_entregue = valor_recebido - valor_total) "
            "OR (forma_pagamento <> 'dinheiro' "
            "AND valor_recebido IS NULL "
            "AND troco_entregue IS NULL)",
            name="ck_sales_pagamento_dinheiro",
        ),
        Index("ix_sales_empresa_data", "empresa_id", "data_venda"),
        Index(
            "ix_sales_empresa_status_data",
            "empresa_id",
            "status",
            "data_venda",
        ),
        Index(
            "ix_sales_empresa_pagamento_data",
            "empresa_id",
            "forma_pagamento",
            "data_venda",
        ),
        Index(
            "ix_sales_empresa_cliente_data",
            "empresa_id",
            "cliente_id",
            "data_venda",
        ),
        Index(
            "uq_sales_empresa_cobranca_externa",
            "empresa_id",
            "provedor_pagamento",
            "cobranca_externa_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    usuario_id: Mapped[int] = mapped_column(index=True)
    caixa_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    cliente_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    desconto: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    forma_pagamento: Mapped[str] = mapped_column(
        String(30),
        default="dinheiro",
    )
    valor_recebido: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    troco_entregue: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(30), default="pago", index=True)
    codigo_pix: Mapped[str | None] = mapped_column(String(600), nullable=True)
    provedor_pagamento: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )
    referencia_pagamento: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )
    cobranca_externa_id: Mapped[str | None] = mapped_column(
        String(180),
        nullable=True,
    )
    status_cobranca: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )
    data_pagamento: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    data_venda: Mapped[datetime] = mapped_column(DateTime, default=data_atual)

    itens = relationship(
        "ItemVenda",
        back_populates="venda",
        cascade="all, delete-orphan",
    )
    caixa = relationship("Caixa", back_populates="vendas")
    cliente = relationship(
        "Cliente",
        back_populates="vendas",
        overlaps="caixa,vendas",
    )
    cancelamento = relationship(
        "CancelamentoVenda",
        back_populates="venda",
        uselist=False,
        cascade="all, delete-orphan",
    )
    devolucoes = relationship(
        "DevolucaoVenda",
        back_populates="venda",
        cascade="all, delete-orphan",
    )


class ItemVenda(BaseModelo):
    __tablename__ = "sale_items"
    __table_args__ = (
        UniqueConstraint("id", "empresa_id", name="uq_sale_items_id_empresa"),
        ForeignKeyConstraint(
            ["venda_id", "empresa_id"],
            ["sales.id", "sales.empresa_id"],
            name="fk_sale_items_venda_empresa",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["produto_id", "empresa_id"],
            ["products.id", "products.empresa_id"],
            name="fk_sale_items_produto_empresa",
            ondelete="RESTRICT",
        ),
        CheckConstraint("quantidade > 0", name="ck_sale_items_quantidade"),
        CheckConstraint(
            "valor_unitario >= 0 AND valor_total = valor_unitario * quantidade",
            name="ck_sale_items_valores",
        ),
        CheckConstraint(
            "custo_unitario >= 0 AND custo_total = custo_unitario * quantidade",
            name="ck_sale_items_custos",
        ),
        Index("ix_sale_items_empresa_venda", "empresa_id", "venda_id"),
        Index("ix_sale_items_empresa_produto", "empresa_id", "produto_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    venda_id: Mapped[int] = mapped_column(index=True)
    produto_id: Mapped[int] = mapped_column(index=True)
    codigo_barras: Mapped[str] = mapped_column(String(80))
    nome_produto: Mapped[str] = mapped_column(String(180))
    quantidade: Mapped[int] = mapped_column(Integer)
    valor_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valor_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    custo_unitario: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0,
    )
    custo_total: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0,
    )

    venda = relationship("Venda", back_populates="itens")


class CancelamentoVenda(BaseModelo):
    __tablename__ = "sale_cancellations"
    __table_args__ = (
        UniqueConstraint(
            "venda_id",
            "empresa_id",
            name="uq_sale_cancellations_venda_empresa",
        ),
        ForeignKeyConstraint(
            ["venda_id", "empresa_id"],
            ["sales.id", "sales.empresa_id"],
            name="fk_sale_cancellations_venda_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["users.id", "users.empresa_id"],
            name="fk_sale_cancellations_usuario_empresa",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_sale_cancellations_empresa_data",
            "empresa_id",
            "data_cancelamento",
        ),
        Index(
            "ix_sale_cancellations_empresa_usuario_data",
            "empresa_id",
            "usuario_id",
            "data_cancelamento",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    venda_id: Mapped[int] = mapped_column(index=True)
    usuario_id: Mapped[int] = mapped_column(index=True)
    motivo: Mapped[str] = mapped_column(Text)
    data_cancelamento: Mapped[datetime] = mapped_column(
        DateTime,
        default=data_atual,
    )

    venda = relationship("Venda", back_populates="cancelamento")
