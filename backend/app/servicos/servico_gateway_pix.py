from dataclasses import dataclass
from decimal import Decimal

import httpx
from fastapi import HTTPException

from app.modelos.pagamento import ConfiguracaoPagamento
from app.modelos.usuario import Usuario
from app.modelos.venda import Venda
from app.servicos.servico_criptografia import descriptografar_segredo
from app.servicos.servico_pagamentos import url_webhook_configuracao
from app.servicos.servico_pix import gerar_codigo_pix


URL_MERCADO_PAGO = "https://api.mercadopago.com"


@dataclass
class CobrancaPix:
    id_externo: str
    status: str
    codigo_pix: str
    dados_provedor: dict


def _erro_gateway(resposta: httpx.Response) -> HTTPException:
    try:
        dados = resposta.json()
        mensagem = dados.get("message") or dados.get("error")
        causas = dados.get("cause") or []
        if not mensagem and causas:
            mensagem = causas[0].get("description")
    except ValueError:
        mensagem = None
    return HTTPException(
        502,
        "O provedor de pagamento recusou a cobranca"
        + (f": {mensagem}" if mensagem else "."),
    )


def _token_api(configuracao: ConfiguracaoPagamento) -> str:
    token = descriptografar_segredo(
        configuracao.token_api_criptografado
    )
    if not token:
        raise HTTPException(
            422,
            "Configure o Access Token do provedor de pagamento.",
        )
    return token


def criar_cobranca_mercado_pago(
    configuracao: ConfiguracaoPagamento,
    venda: Venda,
    usuario: Usuario,
    url_base_requisicao: str,
) -> CobrancaPix:
    token = _token_api(configuracao)
    corpo = {
        "transaction_amount": float(Decimal(venda.valor_total)),
        "description": f"Venda {venda.id} - Novaris One",
        "payment_method_id": "pix",
        "external_reference": venda.referencia_pagamento,
        "payer": {"email": usuario.email},
    }
    url_webhook = url_webhook_configuracao(
        configuracao,
        url_base_requisicao,
    )
    if url_webhook and not (
        "localhost" in url_webhook or "127.0.0.1" in url_webhook
    ):
        separador = "&" if "?" in url_webhook else "?"
        corpo["notification_url"] = (
            f"{url_webhook}{separador}source_news=webhooks"
        )

    try:
        resposta = httpx.post(
            f"{URL_MERCADO_PAGO}/v1/payments",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Idempotency-Key": venda.referencia_pagamento,
            },
            json=corpo,
            timeout=20,
        )
    except httpx.RequestError as erro:
        raise HTTPException(
            503,
            "Nao foi possivel conectar ao Mercado Pago.",
        ) from erro
    if resposta.status_code >= 400:
        raise _erro_gateway(resposta)

    dados = resposta.json()
    transacao = (
        dados.get("point_of_interaction", {})
        .get("transaction_data", {})
    )
    codigo_pix = transacao.get("qr_code")
    if not dados.get("id") or not codigo_pix:
        raise HTTPException(
            502,
            "O Mercado Pago nao devolveu uma cobranca PIX valida.",
        )
    return CobrancaPix(
        id_externo=str(dados["id"]),
        status=str(dados.get("status") or "pending"),
        codigo_pix=codigo_pix,
        dados_provedor=dados,
    )


def criar_cobranca_pix(
    configuracao: ConfiguracaoPagamento,
    venda: Venda,
    usuario: Usuario,
    url_base_requisicao: str = "",
) -> CobrancaPix:
    if configuracao.provedor == "mercado_pago":
        return criar_cobranca_mercado_pago(
            configuracao,
            venda,
            usuario,
            url_base_requisicao,
        )

    chave_pix = descriptografar_segredo(
        configuracao.chave_pix_criptografada
    )
    codigo_pix = gerar_codigo_pix(
        chave_pix,
        Decimal(venda.valor_total),
        venda.id,
        usuario.empresa.nome,
    )
    return CobrancaPix(
        id_externo=venda.referencia_pagamento,
        status="pending",
        codigo_pix=codigo_pix,
        dados_provedor={},
    )


def consultar_pagamento_mercado_pago(
    configuracao: ConfiguracaoPagamento,
    cobranca_externa_id: str,
) -> dict:
    token = _token_api(configuracao)
    try:
        resposta = httpx.get(
            f"{URL_MERCADO_PAGO}/v1/payments/{cobranca_externa_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
    except httpx.RequestError as erro:
        raise HTTPException(
            503,
            "Nao foi possivel validar o pagamento no Mercado Pago.",
        ) from erro
    if resposta.status_code >= 400:
        raise _erro_gateway(resposta)
    return resposta.json()
