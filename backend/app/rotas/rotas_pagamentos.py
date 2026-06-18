import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.autenticacao.seguranca import obter_usuario_logado
from app.banco.conexao import obter_sessao_banco
from app.esquemas.pagamento import (
    ConfiguracaoPagamentoCriacao,
    ConfiguracaoPagamentoResposta,
    WebhookPagamentoResposta,
)
from app.modelos.usuario import Usuario
from app.servicos.servico_pagamentos import (
    obter_configuracao_modelo,
    resposta_configuracao,
    salvar_configuracao,
)
from app.servicos.servico_permissoes import garantir_permissao
from app.servicos.servico_webhook_pagamentos import (
    processar_webhook_pagamento,
)


roteador_pagamentos = APIRouter(
    prefix="/pagamentos",
    tags=["Pagamentos"],
)


@roteador_pagamentos.get(
    "/configuracao",
    response_model=ConfiguracaoPagamentoResposta,
)
def consultar_configuracao(
    requisicao: Request,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "pagamentos_gerenciar")
    configuracao = obter_configuracao_modelo(usuario.empresa_id, sessao)
    return resposta_configuracao(
        configuracao,
        str(requisicao.base_url).rstrip("/"),
    )


@roteador_pagamentos.put(
    "/configuracao",
    response_model=ConfiguracaoPagamentoResposta,
)
def atualizar_configuracao(
    dados: ConfiguracaoPagamentoCriacao,
    requisicao: Request,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "pagamentos_gerenciar")
    configuracao = salvar_configuracao(dados, usuario, sessao)
    return resposta_configuracao(
        configuracao,
        str(requisicao.base_url).rstrip("/"),
    )


@roteador_pagamentos.post(
    "/webhooks/{provedor}/{token_webhook}",
    response_model=WebhookPagamentoResposta,
    include_in_schema=False,
)
async def receber_webhook_pagamento(
    provedor: str,
    token_webhook: str,
    requisicao: Request,
    sessao: Session = Depends(obter_sessao_banco),
):
    corpo_bruto = await requisicao.body()
    try:
        payload = json.loads(corpo_bruto or b"{}")
    except json.JSONDecodeError as erro:
        raise HTTPException(400, "O webhook enviou um JSON invalido.") from erro
    return processar_webhook_pagamento(
        provedor,
        token_webhook,
        payload,
        corpo_bruto,
        dict(requisicao.query_params),
        {chave.lower(): valor for chave, valor in requisicao.headers.items()},
        sessao,
    )
