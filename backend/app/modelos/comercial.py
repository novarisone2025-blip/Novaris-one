from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
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


class PedidoCompra(BaseModelo):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint("id", "empresa_id", name="uq_purchase_orders_id_empresa"),
        ForeignKeyConstraint(
            ["fornecedor_id", "empresa_id"],
            ["suppliers.id", "suppliers.empresa_id"],
            name="fk_purchase_orders_fornecedor_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["users.id", "users.empresa_id"],
            name="fk_purchase_orders_usuario_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["usuario_recebimento_id", "empresa_id"],
            ["users.id", "users.empresa_id"],
            name="fk_purchase_orders_recebedor_empresa",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('pendente', 'enviado', 'recebido', 'cancelado')",
            name="ck_purchase_orders_status",
        ),
        CheckConstraint("valor_total >= 0", name="ck_purchase_orders_total"),
        Index("ix_purchase_orders_empresa_status", "empresa_id", "status"),
        Index("ix_purchase_orders_empresa_data", "empresa_id", "data_criacao"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    fornecedor_id: Mapped[int] = mapped_column(index=True)
    usuario_id: Mapped[int] = mapped_column(index=True)
    usuario_recebimento_id: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pendente")
    valor_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_criacao: Mapped[datetime] = mapped_column(DateTime, default=data_atual)
    data_envio: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    data_recebimento: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    data_cancelamento: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    itens = relationship(
        "ItemPedidoCompra",
        back_populates="pedido",
        cascade="all, delete-orphan",
    )
    fornecedor = relationship("Fornecedor")


class ItemPedidoCompra(BaseModelo):
    __tablename__ = "purchase_order_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["pedido_id", "empresa_id"],
            ["purchase_orders.id", "purchase_orders.empresa_id"],
            name="fk_purchase_order_items_pedido_empresa",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["produto_id", "empresa_id"],
            ["products.id", "products.empresa_id"],
            name="fk_purchase_order_items_produto_empresa",
            ondelete="RESTRICT",
        ),
        CheckConstraint("quantidade > 0", name="ck_purchase_order_items_quantidade"),
        CheckConstraint(
            "custo_unitario >= 0 AND valor_total = custo_unitario * quantidade",
            name="ck_purchase_order_items_valores",
        ),
        Index("ix_purchase_order_items_empresa_pedido", "empresa_id", "pedido_id"),
        Index("ix_purchase_order_items_empresa_produto", "empresa_id", "produto_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    pedido_id: Mapped[int] = mapped_column(index=True)
    produto_id: Mapped[int] = mapped_column(index=True)
    nome_produto: Mapped[str] = mapped_column(String(180))
    codigo_barras: Mapped[str] = mapped_column(String(80))
    quantidade: Mapped[int] = mapped_column(Integer)
    custo_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valor_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    pedido = relationship("PedidoCompra", back_populates="itens")


class Orcamento(BaseModelo):
    __tablename__ = "quotes"
    __table_args__ = (
        UniqueConstraint("id", "empresa_id", name="uq_quotes_id_empresa"),
        ForeignKeyConstraint(
            ["cliente_id", "empresa_id"],
            ["customers.id", "customers.empresa_id"],
            name="fk_quotes_cliente_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["users.id", "users.empresa_id"],
            name="fk_quotes_usuario_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["venda_id", "empresa_id"],
            ["sales.id", "sales.empresa_id"],
            name="fk_quotes_venda_empresa",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('pendente', 'convertido', 'cancelado', 'expirado')",
            name="ck_quotes_status",
        ),
        CheckConstraint(
            "subtotal >= 0 AND desconto >= 0 AND valor_total >= 0 "
            "AND valor_total = subtotal - desconto",
            name="ck_quotes_valores",
        ),
        Index("ix_quotes_empresa_status_validade", "empresa_id", "status", "validade"),
        Index("ix_quotes_empresa_cliente", "empresa_id", "cliente_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    cliente_id: Mapped[int | None] = mapped_column(nullable=True)
    usuario_id: Mapped[int] = mapped_column(index=True)
    venda_id: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pendente")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    desconto: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    validade: Mapped[date] = mapped_column(Date)
    data_criacao: Mapped[datetime] = mapped_column(DateTime, default=data_atual)
    data_conversao: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    itens = relationship(
        "ItemOrcamento",
        back_populates="orcamento",
        cascade="all, delete-orphan",
    )
    cliente = relationship("Cliente")


class ItemOrcamento(BaseModelo):
    __tablename__ = "quote_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["orcamento_id", "empresa_id"],
            ["quotes.id", "quotes.empresa_id"],
            name="fk_quote_items_orcamento_empresa",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["produto_id", "empresa_id"],
            ["products.id", "products.empresa_id"],
            name="fk_quote_items_produto_empresa",
            ondelete="RESTRICT",
        ),
        CheckConstraint("quantidade > 0", name="ck_quote_items_quantidade"),
        CheckConstraint(
            "valor_unitario >= 0 AND desconto >= 0 "
            "AND valor_total = valor_unitario * quantidade - desconto "
            "AND valor_total >= 0",
            name="ck_quote_items_valores",
        ),
        Index("ix_quote_items_empresa_orcamento", "empresa_id", "orcamento_id"),
        Index("ix_quote_items_empresa_produto", "empresa_id", "produto_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    orcamento_id: Mapped[int] = mapped_column(index=True)
    produto_id: Mapped[int] = mapped_column(index=True)
    nome_produto: Mapped[str] = mapped_column(String(180))
    codigo_barras: Mapped[str] = mapped_column(String(80))
    quantidade: Mapped[int] = mapped_column(Integer)
    valor_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    desconto: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    orcamento = relationship("Orcamento", back_populates="itens")
