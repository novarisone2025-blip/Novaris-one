from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ItemDevolvidoCriacao(BaseModel):
    item_venda_id: int
    quantidade: int = Field(gt=0)


class ItemTrocaCriacao(BaseModel):
    codigo_barras: str = Field(min_length=1, max_length=80)
    quantidade: int = Field(gt=0)


class DevolucaoVendaCriacao(BaseModel):
    tipo: Literal["devolucao", "troca"]
    motivo: str = Field(min_length=5, max_length=500)
    itens_devolvidos: list[ItemDevolvidoCriacao] = Field(min_length=1)
    itens_novos: list[ItemTrocaCriacao] = Field(default_factory=list)
    forma_pagamento: Literal["dinheiro", "pix", "debito", "credito"] | None = None

    @model_validator(mode="after")
    def validar_troca(self):
        if self.tipo == "troca" and not self.itens_novos:
            raise ValueError("Adicione pelo menos um produto novo para a troca.")
        if self.tipo == "devolucao" and self.itens_novos:
            raise ValueError("Devolucoes nao podem conter produtos novos.")
        return self


class ItemVendaDetalheResposta(BaseModel):
    id: int
    produto_id: int
    nome_produto: str
    codigo_barras: str
    quantidade_vendida: int
    quantidade_ja_devolvida: int
    quantidade_disponivel_devolucao: int
    valor_unitario: Decimal


class VendaParaDevolucaoResposta(BaseModel):
    id: int
    status: str
    forma_pagamento: str
    valor_total: Decimal
    data_venda: datetime
    nome_usuario: str
    itens: list[ItemVendaDetalheResposta]


class ItemOperacaoResposta(BaseModel):
    produto_id: int
    nome_produto: str
    codigo_barras: str
    direcao: str
    quantidade: int
    valor_unitario: Decimal


class DevolucaoVendaResposta(BaseModel):
    id: int
    venda_id: int
    tipo: str
    motivo: str
    credito_devolvido: Decimal
    valor_novos_itens: Decimal
    valor_estornado: Decimal
    valor_adicional: Decimal
    forma_pagamento: str
    usuario_id: int
    nome_usuario: str
    caixa_id: int
    data_operacao: datetime
    itens: list[ItemOperacaoResposta]


class FiltrosRelatorioVendas(BaseModel):
    periodo: Literal["dia", "semana", "mes", "personalizado"] = "mes"
    data_inicial: date | None = None
    data_final: date | None = None
    produto_id: int | None = None
    categoria: str | None = None
    usuario_id: int | None = None
    caixa_id: int | None = None
    forma_pagamento: str | None = None


class ProdutoMaisVendidoResposta(BaseModel):
    produto_id: int
    nome: str
    codigo_barras: str
    categoria: str
    quantidade: int
    faturamento: Decimal


class RelatorioAvancadoResposta(BaseModel):
    data_inicial: date
    data_final: date
    faturamento: Decimal
    lucro: Decimal
    quantidade_vendida: int
    quantidade_vendas: int
    ticket_medio: Decimal
    produtos_mais_vendidos: list[ProdutoMaisVendidoResposta]


class BackupResposta(BaseModel):
    id: int
    tipo: str
    nome_arquivo: str
    tamanho_bytes: int
    hash_sha256: str
    data_criacao: datetime


class RestauracaoBackupResposta(BaseModel):
    backup_id: int
    restaurado_em: datetime
    produtos_atualizados: int
    fornecedores_atualizados: int
    usuarios_atualizados: int
