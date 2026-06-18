from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProdutoCriacao(BaseModel):
    codigo_barras: str = Field(min_length=1, max_length=80)
    nome: str = Field(min_length=2, max_length=180)
    categoria: str = Field(default="Sem categoria", min_length=2, max_length=100)
    quantidade: int = Field(default=0, ge=0)
    estoque_minimo: int = Field(default=0, ge=0)
    preco: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    preco_compra: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    fornecedor_id: int | None = None
    imagem_url: str | None = Field(default=None, max_length=500)


class ProdutoAtualizacao(BaseModel):
    codigo_barras: str = Field(min_length=1, max_length=80)
    nome: str = Field(min_length=2, max_length=180)
    categoria: str = Field(default="Sem categoria", min_length=2, max_length=100)
    preco: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    preco_compra: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    fornecedor_id: int | None = None
    estoque_minimo: int = Field(default=0, ge=0)
    imagem_url: str | None = Field(default=None, max_length=500)


class ProdutoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo_barras: str
    nome: str
    categoria: str
    quantidade: int
    estoque_minimo: int
    preco: Decimal
    preco_compra: Decimal
    fornecedor_id: int | None
    imagem_url: str | None
    ativo: bool
    data_criacao: datetime
    data_atualizacao: datetime


class MovimentacaoCriacao(BaseModel):
    tipo: Literal["entrada", "saida", "venda"]
    quantidade: int = Field(gt=0)


class ResultadoMovimentacao(BaseModel):
    mensagem: str
    quantidade_atual: int


class MovimentacaoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome_produto: str
    codigo_barras: str
    tipo: str
    quantidade: int
    quantidade_anterior: int
    quantidade_atual: int
    data_movimentacao: datetime
    nome_usuario: str
    origem: str


class AlertaEstoqueResposta(BaseModel):
    produto_id: int
    nome: str
    codigo_barras: str
    quantidade: int
    estoque_minimo: int
    quantidade_faltante: int
