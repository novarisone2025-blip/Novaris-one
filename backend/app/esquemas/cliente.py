from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ClienteDados(BaseModel):
    nome: str = Field(min_length=2, max_length=160)
    documento: str | None = Field(default=None, max_length=30)
    telefone: str | None = Field(default=None, max_length=30)
    whatsapp: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    endereco: str | None = Field(default=None, max_length=300)
    observacoes: str | None = Field(default=None, max_length=2000)


class ClienteCriacao(ClienteDados):
    pass


class ClienteAtualizacao(ClienteDados):
    ativo: bool = True


class ClienteResposta(ClienteDados):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ativo: bool
    data_criacao: datetime
    data_atualizacao: datetime
    total_gasto: Decimal = Decimal("0")
    quantidade_compras: int = 0
    ticket_medio: Decimal = Decimal("0")
    ultima_compra: datetime | None = None


class ProdutoPreferidoCliente(BaseModel):
    nome: str
    codigo_barras: str
    quantidade: int


class CompraCliente(BaseModel):
    venda_id: int
    data_venda: datetime
    valor_total: Decimal
    forma_pagamento: str
    quantidade_itens: int


class ClienteDetalhe(ClienteResposta):
    historico_compras: list[CompraCliente] = Field(default_factory=list)
    produtos_mais_comprados: list[ProdutoPreferidoCliente] = Field(
        default_factory=list
    )
