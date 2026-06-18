from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


FormaPagamento = Literal["dinheiro", "pix", "debito", "credito"]


class ItemVendaCriacao(BaseModel):
    codigo_barras: str = Field(min_length=1, max_length=80)
    quantidade: int = Field(gt=0)


class VendaCriacao(BaseModel):
    itens: list[ItemVendaCriacao] = Field(default_factory=list)
    cliente_id: int | None = Field(default=None, gt=0)
    desconto: Decimal = Field(default=0, ge=0, max_digits=12, decimal_places=2)
    forma_pagamento: FormaPagamento = "dinheiro"
    valor_recebido: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
    )

    # Mantem compatibilidade com a primeira versao da rota.
    codigo_barras: str | None = Field(default=None, max_length=80)
    quantidade: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validar_itens(self):
        if not self.itens and self.codigo_barras and self.quantidade:
            self.itens = [
                ItemVendaCriacao(
                    codigo_barras=self.codigo_barras,
                    quantidade=self.quantidade,
                )
            ]
        if not self.itens:
            raise ValueError("Adicione pelo menos um produto ao carrinho.")
        return self


class CancelamentoVendaCriacao(BaseModel):
    motivo: str = Field(min_length=5, max_length=500)


class ProdutoVendaResposta(BaseModel):
    id: int
    codigo_barras: str
    nome: str
    preco: Decimal
    quantidade: int
    imagem_url: str | None


class ItemVendaResposta(BaseModel):
    produto_id: int
    nome_produto: str
    codigo_barras: str
    quantidade: int
    valor_unitario: Decimal
    valor_total: Decimal
    quantidade_atual: int


class VendaResposta(BaseModel):
    id: int
    itens: list[ItemVendaResposta]
    subtotal: Decimal
    desconto: Decimal
    valor_total: Decimal
    forma_pagamento: FormaPagamento
    valor_recebido: Decimal | None = None
    troco_entregue: Decimal | None = None
    status: str
    codigo_pix: str | None = None
    qr_code_pix: str | None = None
    cobranca_externa_id: str | None = None
    status_cobranca: str | None = None
    confirmacao_automatica: bool = False
    data_venda: datetime
    cliente_id: int | None = None

    # Campos de conveniencia para clientes antigos de item unico.
    nome_produto: str | None = None
    codigo_barras: str | None = None
    quantidade: int | None = None
    valor_unitario: Decimal | None = None
    quantidade_atual: int | None = None


class StatusPagamentoVendaResposta(BaseModel):
    venda_id: int
    status: str
    status_cobranca: str | None = None
    data_pagamento: datetime | None = None


class VendaFinanceiraResposta(BaseModel):
    id: int
    subtotal: Decimal
    desconto: Decimal
    valor_total: Decimal
    forma_pagamento: str
    valor_recebido: Decimal | None = None
    troco_entregue: Decimal | None = None
    status: str
    data_venda: datetime
    quantidade_itens: int
    usuario_id: int
    nome_usuario: str
    cargo_usuario: str
    caixa_id: int | None = None
    cliente_id: int | None = None
    nome_cliente: str | None = None
    data_cancelamento: datetime | None = None
    motivo_cancelamento: str | None = None
    usuario_cancelamento_id: int | None = None
    nome_usuario_cancelamento: str | None = None


class CancelamentoVendaResposta(BaseModel):
    venda_id: int
    status: str
    motivo: str
    data_cancelamento: datetime
    usuario_id: int
    nome_usuario: str
    produtos_devolvidos: int


class ResumoOperadorResposta(BaseModel):
    usuario_id: int
    nome_usuario: str
    cargo_usuario: str
    total_vendido: Decimal
    quantidade_vendas: int
    total_descontos: Decimal
    primeiro_horario: datetime | None
    ultimo_horario: datetime | None
    formas_pagamento: dict[str, Decimal]
