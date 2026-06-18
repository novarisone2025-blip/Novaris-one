from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class AberturaCaixa(BaseModel):
    valor_inicial: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class FechamentoCaixa(BaseModel):
    valor_real: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class MovimentacaoCaixaCriacao(BaseModel):
    valor: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    motivo: str = Field(min_length=5, max_length=500)


class MovimentacaoCaixaResposta(BaseModel):
    id: int
    caixa_id: int
    usuario_id: int
    nome_usuario: str
    tipo: str
    motivo: str
    valor: Decimal
    data_movimento: datetime


class CaixaResposta(BaseModel):
    id: int
    usuario_id: int
    nome_usuario: str
    cargo_usuario: str
    status: str
    valor_inicial: Decimal
    total_dinheiro: Decimal
    total_recebido_dinheiro: Decimal
    total_troco_entregue: Decimal
    total_pix: Decimal
    total_debito: Decimal
    total_credito: Decimal
    total_descontos: Decimal
    total_cancelamentos: Decimal
    total_sangrias: Decimal
    total_reforcos: Decimal
    total_devolucoes_dinheiro: Decimal
    total_devolucoes: Decimal
    total_adicionais_troca: Decimal
    quantidade_vendas: int
    total_vendido: Decimal
    quantidade_cancelamentos: int
    vendas_pendentes: int
    valor_esperado: Decimal
    valor_real: Decimal | None
    diferenca: Decimal | None
    situacao_diferenca: str
    data_abertura: datetime
    data_fechamento: datetime | None
    movimentacoes_caixa: list[MovimentacaoCaixaResposta] = Field(
        default_factory=list
    )
