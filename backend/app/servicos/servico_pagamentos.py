import secrets

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.configuracao.configuracoes import configuracoes
from app.esquemas.pagamento import ConfiguracaoPagamentoCriacao
from app.modelos.pagamento import ConfiguracaoPagamento
from app.modelos.usuario import Usuario
from app.servicos.servico_criptografia import (
    criptografar_segredo,
    descriptografar_segredo,
    mascarar_segredo,
)


def obter_configuracao_modelo(
    empresa_id: int,
    sessao: Session,
) -> ConfiguracaoPagamento | None:
    return sessao.scalar(
        select(ConfiguracaoPagamento).where(
            ConfiguracaoPagamento.empresa_id == empresa_id
        )
    )


def url_webhook_configuracao(
    configuracao: ConfiguracaoPagamento,
    url_base_requisicao: str = "",
) -> str | None:
    if not configuracao.token_webhook:
        return None
    url_base = configuracoes.url_publica_api or url_base_requisicao.rstrip("/")
    if not url_base:
        return None
    return (
        f"{url_base}/pagamentos/webhooks/"
        f"{configuracao.provedor}/{configuracao.token_webhook}"
    )


def resposta_configuracao(
    configuracao: ConfiguracaoPagamento | None,
    url_base_requisicao: str = "",
) -> dict:
    if not configuracao:
        return {"configurado": False}
    chave = descriptografar_segredo(
        configuracao.chave_pix_criptografada
    )
    return {
        "configurado": True,
        "provedor": configuracao.provedor,
        "chave_pix_mascarada": mascarar_segredo(chave),
        "possui_token_api": bool(configuracao.token_api_criptografado),
        "possui_client_id": bool(configuracao.client_id_criptografado),
        "possui_client_secret": bool(
            configuracao.client_secret_criptografado
        ),
        "possui_segredo_webhook": bool(
            configuracao.segredo_webhook_criptografado
        ),
        "confirmacao_automatica": (
            configuracao.provedor == "mercado_pago"
            and bool(configuracao.token_api_criptografado)
            and configuracao.ativo
        ),
        "webhook_url": url_webhook_configuracao(
            configuracao,
            url_base_requisicao,
        ),
        "ativo": configuracao.ativo,
        "data_atualizacao": configuracao.data_atualizacao,
    }


def salvar_configuracao(
    dados: ConfiguracaoPagamentoCriacao,
    usuario: Usuario,
    sessao: Session,
) -> ConfiguracaoPagamento:
    configuracao = obter_configuracao_modelo(usuario.empresa_id, sessao)
    if not configuracao:
        configuracao = ConfiguracaoPagamento(
            empresa_id=usuario.empresa_id,
            token_webhook=secrets.token_urlsafe(32),
        )
    elif not configuracao.token_webhook:
        configuracao.token_webhook = secrets.token_urlsafe(32)

    chave_pix = (dados.chave_pix or "").strip()
    if chave_pix:
        if len(chave_pix) < 3:
            raise HTTPException(422, "Informe uma chave PIX valida.")
        configuracao.chave_pix_criptografada = criptografar_segredo(chave_pix)
    elif not configuracao.chave_pix_criptografada:
        raise HTTPException(422, "Informe a chave PIX da empresa.")

    configuracao.provedor = dados.provedor
    for atributo, valor in (
        ("token_api_criptografado", dados.token_api),
        ("client_id_criptografado", dados.client_id),
        ("client_secret_criptografado", dados.client_secret),
        ("segredo_webhook_criptografado", dados.segredo_webhook),
    ):
        if valor and valor.strip():
            setattr(configuracao, atributo, criptografar_segredo(valor.strip()))

    if (
        dados.provedor == "mercado_pago"
        and not configuracao.token_api_criptografado
    ):
        raise HTTPException(
            422,
            "Informe o Access Token do Mercado Pago.",
        )
    configuracao.ativo = dados.ativo
    sessao.add(configuracao)
    sessao.commit()
    sessao.refresh(configuracao)
    return configuracao
