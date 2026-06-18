from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco.conexao import BaseModelo


def data_atual():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DevolucaoVenda(BaseModelo):
    __tablename__ = "sale_returns"
    __table_args__ = (
        UniqueConstraint("id", "empresa_id", name="uq_sale_returns_id_empresa"),
        ForeignKeyConstraint(
            ["venda_id", "empresa_id"],
            ["sales.id", "sales.empresa_id"],
            name="fk_sale_returns_venda_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["users.id", "users.empresa_id"],
            name="fk_sale_returns_usuario_empresa",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["caixa_id", "empresa_id", "usuario_id"],
            [
                "cash_registers.id",
                "cash_registers.empresa_id",
                "cash_registers.usuario_id",
            ],
            name="fk_sale_returns_caixa_usuario_empresa",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "tipo IN ('devolucao', 'troca')",
            name="ck_sale_returns_tipo",
        ),
        CheckConstraint(
            "credito_devolvido >= 0 AND valor_novos_itens >= 0 "
            "AND valor_estornado >= 0 AND valor_adicional >= 0",
            name="ck_sale_returns_valores",
        ),
        Index("ix_sale_returns_empresa_data", "empresa_id", "data_operacao"),
        Index("ix_sale_returns_empresa_venda", "empresa_id", "venda_id"),
        Index(
            "ix_sale_returns_empresa_usuario_data",
            "empresa_id",
            "usuario_id",
            "data_operacao",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    venda_id: Mapped[int] = mapped_column(index=True)
    usuario_id: Mapped[int] = mapped_column(index=True)
    caixa_id: Mapped[int] = mapped_column(index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    motivo: Mapped[str] = mapped_column(Text)
    credito_devolvido: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valor_novos_itens: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valor_estornado: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valor_adicional: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    forma_pagamento: Mapped[str] = mapped_column(String(30))
    data_operacao: Mapped[datetime] = mapped_column(DateTime, default=data_atual)

    venda = relationship("Venda", back_populates="devolucoes")
    itens = relationship(
        "ItemDevolucaoVenda",
        back_populates="operacao",
        cascade="all, delete-orphan",
    )


class ItemDevolucaoVenda(BaseModelo):
    __tablename__ = "sale_return_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["devolucao_id", "empresa_id"],
            ["sale_returns.id", "sale_returns.empresa_id"],
            name="fk_sale_return_items_operacao_empresa",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["produto_id", "empresa_id"],
            ["products.id", "products.empresa_id"],
            name="fk_sale_return_items_produto_empresa",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "direcao IN ('devolvido', 'novo')",
            name="ck_sale_return_items_direcao",
        ),
        CheckConstraint("quantidade > 0", name="ck_sale_return_items_quantidade"),
        CheckConstraint(
            "valor_unitario >= 0 AND custo_unitario >= 0",
            name="ck_sale_return_items_valores",
        ),
        Index(
            "ix_sale_return_items_empresa_operacao",
            "empresa_id",
            "devolucao_id",
        ),
        Index(
            "ix_sale_return_items_empresa_produto",
            "empresa_id",
            "produto_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    devolucao_id: Mapped[int] = mapped_column(index=True)
    item_venda_id: Mapped[int | None] = mapped_column(
        ForeignKey("sale_items.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    produto_id: Mapped[int] = mapped_column(index=True)
    direcao: Mapped[str] = mapped_column(String(20))
    nome_produto: Mapped[str] = mapped_column(String(180))
    codigo_barras: Mapped[str] = mapped_column(String(80))
    quantidade: Mapped[int] = mapped_column(Integer)
    valor_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    custo_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    operacao = relationship("DevolucaoVenda", back_populates="itens")


class MovimentacaoCaixa(BaseModelo):
    __tablename__ = "cash_movements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["caixa_id", "empresa_id", "usuario_id"],
            [
                "cash_registers.id",
                "cash_registers.empresa_id",
                "cash_registers.usuario_id",
            ],
            name="fk_cash_movements_caixa_usuario_empresa",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "tipo IN ('sangria', 'reforco')",
            name="ck_cash_movements_tipo",
        ),
        CheckConstraint("valor > 0", name="ck_cash_movements_valor"),
        Index("ix_cash_movements_empresa_data", "empresa_id", "data_movimento"),
        Index("ix_cash_movements_empresa_caixa", "empresa_id", "caixa_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"),
        index=True,
    )
    caixa_id: Mapped[int] = mapped_column(index=True)
    usuario_id: Mapped[int] = mapped_column(index=True)
    tipo: Mapped[str] = mapped_column(String(20))
    motivo: Mapped[str] = mapped_column(Text)
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    data_movimento: Mapped[datetime] = mapped_column(DateTime, default=data_atual)


class BackupEmpresa(BaseModelo):
    __tablename__ = "company_backups"
    __table_args__ = (
        ForeignKeyConstraint(
            ["usuario_id", "empresa_id"],
            ["users.id", "users.empresa_id"],
            name="fk_company_backups_usuario_empresa",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "tipo IN ('automatico', 'manual', 'pre_restauracao')",
            name="ck_company_backups_tipo",
        ),
        Index("ix_company_backups_empresa_data", "empresa_id", "data_criacao"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        index=True,
    )
    usuario_id: Mapped[int] = mapped_column(index=True)
    tipo: Mapped[str] = mapped_column(String(30))
    nome_arquivo: Mapped[str] = mapped_column(String(180))
    hash_sha256: Mapped[str] = mapped_column(String(64))
    tamanho_bytes: Mapped[int] = mapped_column(Integer)
    conteudo: Mapped[bytes] = mapped_column(LargeBinary)
    data_criacao: Mapped[datetime] = mapped_column(DateTime, default=data_atual)
