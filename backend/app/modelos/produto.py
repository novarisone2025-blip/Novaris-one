from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco.conexao import BaseModelo


def data_atual():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Produto(BaseModelo):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint(
            "empresa_id",
            "codigo_barras",
            name="uq_produto_empresa_codigo_barras",
        ),
        UniqueConstraint("id", "empresa_id", name="uq_products_id_empresa"),
        ForeignKeyConstraint(
            ["fornecedor_id", "empresa_id"],
            ["suppliers.id", "suppliers.empresa_id"],
            name="fk_products_fornecedor_empresa",
            ondelete="RESTRICT",
        ),
        CheckConstraint("quantidade >= 0", name="ck_products_quantidade"),
        CheckConstraint(
            "estoque_minimo >= 0",
            name="ck_products_estoque_minimo",
        ),
        CheckConstraint("preco > 0", name="ck_products_preco_venda"),
        CheckConstraint(
            "preco_compra >= 0",
            name="ck_products_preco_compra",
        ),
        Index("ix_products_empresa_nome", "empresa_id", "nome"),
        Index(
            "ix_products_empresa_ativo_nome",
            "empresa_id",
            "ativo",
            "nome",
        ),
        Index(
            "ix_products_empresa_estoque",
            "empresa_id",
            "ativo",
            "quantidade",
            "estoque_minimo",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    codigo_barras: Mapped[str] = mapped_column(String(80), index=True)
    nome: Mapped[str] = mapped_column(String(180))
    categoria: Mapped[str] = mapped_column(
        String(100),
        default="Sem categoria",
    )
    quantidade: Mapped[int] = mapped_column(Integer, default=0)
    estoque_minimo: Mapped[int] = mapped_column(Integer, default=0)
    preco: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    preco_compra: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=0,
    )
    fornecedor_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    imagem_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    data_criacao: Mapped[datetime] = mapped_column(
        DateTime,
        default=data_atual,
    )
    data_atualizacao: Mapped[datetime] = mapped_column(
        DateTime,
        default=data_atual,
        onupdate=data_atual,
    )

    movimentacoes = relationship(
        "MovimentacaoEstoque",
        back_populates="produto",
    )
    fornecedor = relationship("Fornecedor", back_populates="produtos")


class MovimentacaoEstoque(BaseModelo):
    __tablename__ = "stock_movements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["produto_id", "empresa_id"],
            ["products.id", "products.empresa_id"],
            name="fk_stock_movements_produto_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["users.id", "users.empresa_id"],
            name="fk_stock_movements_usuario_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["venda_id", "empresa_id"],
            ["sales.id", "sales.empresa_id"],
            name="fk_stock_movements_venda_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["pedido_compra_id", "empresa_id"],
            ["purchase_orders.id", "purchase_orders.empresa_id"],
            name="fk_stock_movements_pedido_empresa",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "tipo IN ('entrada', 'saida')",
            name="ck_stock_movements_tipo",
        ),
        CheckConstraint(
            "quantidade > 0",
            name="ck_stock_movements_quantidade",
        ),
        CheckConstraint(
            "quantidade_anterior >= 0 AND quantidade_atual >= 0",
            name="ck_stock_movements_saldos",
        ),
        Index(
            "ix_stock_movements_empresa_data",
            "empresa_id",
            "data_movimentacao",
        ),
        Index(
            "ix_stock_movements_empresa_tipo_data",
            "empresa_id",
            "tipo",
            "data_movimentacao",
        ),
        Index(
            "ix_stock_movements_empresa_produto_data",
            "empresa_id",
            "produto_id",
            "data_movimentacao",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    produto_id: Mapped[int] = mapped_column(index=True)
    usuario_id: Mapped[int] = mapped_column(index=True)
    venda_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    pedido_compra_id: Mapped[int | None] = mapped_column(
        nullable=True,
        index=True,
    )
    tipo: Mapped[str] = mapped_column(String(20))
    quantidade: Mapped[int] = mapped_column(Integer)
    quantidade_anterior: Mapped[int] = mapped_column(Integer, default=0)
    quantidade_atual: Mapped[int] = mapped_column(Integer, default=0)
    nome_produto: Mapped[str] = mapped_column(String(180), default="")
    codigo_barras: Mapped[str] = mapped_column(String(80), default="")
    nome_usuario: Mapped[str] = mapped_column(String(120), default="")
    origem: Mapped[str] = mapped_column(String(30), default="estoque")
    data_movimentacao: Mapped[datetime] = mapped_column(
        DateTime,
        default=data_atual,
    )

    produto = relationship("Produto", back_populates="movimentacoes")
