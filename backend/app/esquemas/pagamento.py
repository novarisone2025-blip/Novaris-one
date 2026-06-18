from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ProvedorPagamento = Literal["manual", "mercado_pago", "asaas", "efi"]


class ConfiguracaoPagamentoCriacao(BaseModel):
    provedor: ProvedorPagamento = "manual"
    chave_pix: str | None = Field(default=None, max_length=180)
    token_api: str | None = Field(default=None, max_length=500)
    client_id: str | None = Field(default=None, max_length=300)
    client_secret: str | None = Field(default=None, max_length=500)
    segredo_webhook: str | None = Field(default=None, max_length=500)
    ativo: bool = True


class ConfiguracaoPagamentoResposta(BaseModel):
    configurado: bool
    provedor: str | None = None
    chave_pix_mascarada: str | None = None
    possui_token_api: bool = False
    possui_client_id: bool = False
    possui_client_secret: bool = False
    possui_segredo_webhook: bool = False
    confirmacao_automatica: bool = False
    webhook_url: str | None = None
    ativo: bool = False
    data_atualizacao: datetime | None = None


class WebhookPagamentoResposta(BaseModel):
    recebido: bool
    processado: bool
    status: str
    venda_id: int | None = None
