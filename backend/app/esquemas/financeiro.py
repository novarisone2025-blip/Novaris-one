from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LancamentoCriacao(BaseModel):
    tipo: Literal["entrada", "saida"]
    categoria: str = Field(min_length=2, max_length=80)
    descricao: str = Field(min_length=2, max_length=220)
    valor: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    data_lancamento: datetime | None = None


class LancamentoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | str
    tipo: str
    categoria: str
    descricao: str
    valor: Decimal
    data_lancamento: datetime
    origem: str
    usuario_id: int
    nome_usuario: str
    cargo_usuario: str
    caixa_id: int | None = None
    forma_pagamento: str | None = None
    valor_recebido: Decimal | None = None
    troco_entregue: Decimal | None = None


class ResumoFinanceiroResposta(BaseModel):
    faturamento: Decimal
    custo_produtos: Decimal
    lucro_bruto: Decimal
    outras_entradas: Decimal
    despesas: Decimal
    saldo_caixa: Decimal
    margem_bruta: float
    quantidade_vendas: int
    ticket_medio: Decimal
    data_inicial: date
    data_final: date
