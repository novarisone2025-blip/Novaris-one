from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.esquemas.venda import FormaPagamento


class ItemOrcamentoCriacao(BaseModel):
    produto_id: int = Field(gt=0)
    quantidade: int = Field(gt=0)
    desconto: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)


class OrcamentoCriacao(BaseModel):
    cliente_id: int | None = Field(default=None, gt=0)
    itens: list[ItemOrcamentoCriacao] = Field(min_length=1)
    desconto: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    observacoes: str | None = Field(default=None, max_length=3000)
    validade: date


class ConversaoOrcamento(BaseModel):
    forma_pagamento: FormaPagamento = "dinheiro"


class ItemOrcamentoResposta(BaseModel):
    id: int
    produto_id: int
    nome_produto: str
    codigo_barras: str
    quantidade: int
    valor_unitario: Decimal
    desconto: Decimal
    valor_total: Decimal


class OrcamentoResposta(BaseModel):
    id: int
    cliente_id: int | None
    nome_cliente: str | None
    cliente_documento: str | None
    cliente_telefone: str | None
    cliente_whatsapp: str | None
    cliente_email: str | None
    cliente_endereco: str | None
    usuario_id: int
    nome_usuario: str
    venda_id: int | None
    status: str
    subtotal: Decimal
    desconto: Decimal
    valor_total: Decimal
    observacoes: str | None
    validade: date
    data_criacao: datetime
    data_conversao: datetime | None
    itens: list[ItemOrcamentoResposta]


class CompartilhamentoOrcamento(BaseModel):
    whatsapp_url: str
    email_url: str
