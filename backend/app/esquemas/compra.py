from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


StatusPedido = Literal["pendente", "enviado", "recebido", "cancelado"]


class SugestaoReposicaoResposta(BaseModel):
    produto_id: int
    nome_produto: str
    codigo_barras: str
    fornecedor_id: int | None
    nome_fornecedor: str
    estoque_atual: int
    estoque_minimo: int
    quantidade_sugerida: int
    custo_unitario: Decimal
    custo_estimado: Decimal


class ItemPedidoCompraCriacao(BaseModel):
    produto_id: int = Field(gt=0)
    quantidade: int = Field(gt=0)
    custo_unitario: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )


class PedidoCompraCriacao(BaseModel):
    fornecedor_id: int = Field(gt=0)
    itens: list[ItemPedidoCompraCriacao] = Field(min_length=1)
    observacoes: str | None = Field(default=None, max_length=2000)


class PedidoCompraStatus(BaseModel):
    status: StatusPedido


class ItemPedidoCompraResposta(BaseModel):
    id: int
    produto_id: int
    nome_produto: str
    codigo_barras: str
    quantidade: int
    custo_unitario: Decimal
    valor_total: Decimal


class PedidoCompraResposta(BaseModel):
    id: int
    fornecedor_id: int
    nome_fornecedor: str
    usuario_id: int
    nome_usuario: str
    usuario_recebimento_id: int | None
    nome_usuario_recebimento: str | None
    status: StatusPedido
    valor_total: Decimal
    observacoes: str | None
    data_criacao: datetime
    data_envio: datetime | None
    data_recebimento: datetime | None
    data_cancelamento: datetime | None
    itens: list[ItemPedidoCompraResposta]
