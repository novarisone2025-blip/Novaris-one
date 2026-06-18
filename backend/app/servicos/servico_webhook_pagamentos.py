import hashlib
import hmac
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modelos.pagamento import (
    ConfiguracaoPagamento,
    EventoWebhookPagamento,
)
from app.modelos.usuario import Usuario
from app.modelos.venda import Venda
from app.servicos.servico_criptografia import descriptografar_segredo
from app.servicos.servico_gateway_pix import (
    consultar_pagamento_mercado_pago,
)
from app.servicos.servico_vendas import confirmar_pagamento_venda


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _partes_assinatura(cabecalho: str) -> dict[str, str]:
    partes = {}
    for trecho in cabecalho.split(","):
        chave, separador, valor = trecho.strip().partition("=")
        if separador and chave and valor:
            partes[chave] = valor
    return partes


def validar_assinatura_mercado_pago(
    segredo: str,
    cobranca_id_url: str,
    identificador_requisicao: str,
    assinatura: str,
) -> None:
    partes = _partes_assinatura(assinatura)
    timestamp = partes.get("ts")
    assinatura_recebida = partes.get("v1")
    if not timestamp or not assinatura_recebida:
        raise HTTPException(401, "Assinatura do webhook incompleta.")

    campos = []
    if cobranca_id_url:
        campos.append(f"id:{cobranca_id_url.lower()};")
    if identificador_requisicao:
        campos.append(f"request-id:{identificador_requisicao};")
    campos.append(f"ts:{timestamp};")
    assinatura_calculada = hmac.new(
        segredo.encode("utf-8"),
        "".join(campos).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(
        assinatura_calculada,
        assinatura_recebida,
    ):
        raise HTTPException(401, "Assinatura do webhook invalida.")


def _identificador_cobranca(payload: dict, parametros: dict) -> str:
    identificador = parametros.get("data.id")
    if not identificador:
        identificador = (payload.get("data") or {}).get("id")
    if not identificador:
        raise HTTPException(
            422,
            "A notificacao nao informou o ID do pagamento.",
        )
    return str(identificador)


def _identificador_evento(
    payload: dict,
    identificador_requisicao: str,
    cobranca_id: str,
    hash_payload: str,
) -> str:
    return str(
        payload.get("id")
        or identificador_requisicao
        or f"{cobranca_id}:{payload.get('action', 'payment')}:{hash_payload}"
    )


def _configuracao_webhook(
    provedor: str,
    token_webhook: str,
    sessao: Session,
) -> ConfiguracaoPagamento:
    configuracao = sessao.scalar(
        select(ConfiguracaoPagamento).where(
            ConfiguracaoPagamento.provedor == provedor,
            ConfiguracaoPagamento.token_webhook == token_webhook,
            ConfiguracaoPagamento.ativo.is_(True),
        )
    )
    if not configuracao:
        raise HTTPException(404, "Webhook de pagamento nao encontrado.")
    return configuracao


def _validar_pagamento_da_venda(venda: Venda, pagamento: dict) -> None:
    if str(pagamento.get("id")) != str(venda.cobranca_externa_id):
        raise HTTPException(409, "A cobranca nao pertence a esta venda.")
    if pagamento.get("external_reference") != venda.referencia_pagamento:
        raise HTTPException(
            409,
            "A referencia da cobranca nao corresponde a venda.",
        )
    try:
        valor_gateway = Decimal(
            str(pagamento.get("transaction_amount"))
        ).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        raise HTTPException(409, "O valor da cobranca e invalido.")
    if valor_gateway != Decimal(venda.valor_total).quantize(Decimal("0.01")):
        raise HTTPException(
            409,
            "O valor confirmado nao corresponde ao total da venda.",
        )


def processar_webhook_pagamento(
    provedor: str,
    token_webhook: str,
    payload: dict,
    corpo_bruto: bytes,
    parametros: dict,
    cabecalhos: dict,
    sessao: Session,
) -> dict:
    if provedor != "mercado_pago":
        raise HTTPException(
            422,
            "Confirmacao automatica indisponivel para este provedor.",
        )
    configuracao = _configuracao_webhook(
        provedor,
        token_webhook,
        sessao,
    )
    tipo = str(payload.get("type") or parametros.get("type") or "payment")
    cobranca_id = _identificador_cobranca(payload, parametros)
    identificador_requisicao = cabecalhos.get("x-request-id", "")

    segredo = descriptografar_segredo(
        configuracao.segredo_webhook_criptografado
    )
    if segredo:
        validar_assinatura_mercado_pago(
            segredo,
            str(parametros.get("data.id") or ""),
            identificador_requisicao,
            cabecalhos.get("x-signature", ""),
        )

    hash_payload = hashlib.sha256(corpo_bruto).hexdigest()
    evento_externo_id = _identificador_evento(
        payload,
        identificador_requisicao,
        cobranca_id,
        hash_payload,
    )
    evento = sessao.scalar(
        select(EventoWebhookPagamento).where(
            EventoWebhookPagamento.empresa_id == configuracao.empresa_id,
            EventoWebhookPagamento.provedor == provedor,
            EventoWebhookPagamento.evento_externo_id == evento_externo_id,
        )
    )
    if evento and evento.status == "processado":
        return {
            "recebido": True,
            "processado": True,
            "status": "pago",
            "venda_id": evento.venda_id,
        }
    if not evento:
        evento = EventoWebhookPagamento(
            empresa_id=configuracao.empresa_id,
            provedor=provedor,
            evento_externo_id=evento_externo_id,
            cobranca_externa_id=cobranca_id,
            tipo=tipo,
            status="recebido",
            hash_payload=hash_payload,
        )
        sessao.add(evento)
        sessao.flush()

    if tipo != "payment":
        evento.status = "ignorado"
        evento.mensagem = f"Evento {tipo} nao altera vendas PIX."
        evento.data_processamento = _agora()
        sessao.commit()
        return {
            "recebido": True,
            "processado": False,
            "status": "ignorado",
        }

    pagamento = consultar_pagamento_mercado_pago(
        configuracao,
        cobranca_id,
    )
    venda = sessao.scalar(
        select(Venda)
        .options(selectinload(Venda.itens))
        .where(
            Venda.empresa_id == configuracao.empresa_id,
            Venda.provedor_pagamento == provedor,
            Venda.cobranca_externa_id == cobranca_id,
        )
        .with_for_update()
    )
    if not venda:
        evento.status = "ignorado"
        evento.mensagem = "Cobranca sem venda correspondente nesta empresa."
        evento.data_processamento = _agora()
        sessao.commit()
        return {
            "recebido": True,
            "processado": False,
            "status": "venda_nao_encontrada",
        }

    evento.venda_id = venda.id
    _validar_pagamento_da_venda(venda, pagamento)
    status_gateway = str(pagamento.get("status") or "pending")
    if status_gateway != "approved":
        venda.status_cobranca = (
            "aguardando_pagamento"
            if status_gateway in {"pending", "in_process"}
            else status_gateway
        )
        evento.status = "ignorado"
        evento.mensagem = f"Pagamento ainda esta com status {status_gateway}."
        evento.data_processamento = _agora()
        sessao.commit()
        return {
            "recebido": True,
            "processado": False,
            "status": venda.status_cobranca,
            "venda_id": venda.id,
        }

    usuario = sessao.scalar(
        select(Usuario).where(
            Usuario.id == venda.usuario_id,
            Usuario.empresa_id == venda.empresa_id,
        )
    )
    if not usuario:
        raise HTTPException(
            409,
            "O usuario responsavel pela venda nao foi encontrado.",
        )
    confirmar_pagamento_venda(
        venda,
        usuario,
        sessao,
        "webhook_mercado_pago",
    )
    evento.status = "processado"
    evento.mensagem = "Pagamento confirmado automaticamente."
    evento.data_processamento = _agora()
    sessao.commit()
    return {
        "recebido": True,
        "processado": True,
        "status": "pago",
        "venda_id": venda.id,
    }
