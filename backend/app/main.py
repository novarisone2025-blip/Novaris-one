import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.banco.conexao import BaseModelo, motor_banco
from app.banco.migracoes import aplicar_migracoes_leves
from app.configuracao.configuracoes import configuracoes
from app.configuracao.logs import configurar_logs
from app.rotas.rotas_autenticacao import roteador_autenticacao
from app.rotas.rotas_backup import roteador_backup
from app.rotas.rotas_caixa import roteador_caixa
from app.rotas.rotas_clientes import roteador_clientes
from app.rotas.rotas_compras import roteador_compras
from app.rotas.rotas_dashboard import roteador_dashboard
from app.rotas.rotas_estoque import roteador_estoque
from app.rotas.rotas_financeiro import roteador_financeiro
from app.rotas.rotas_fornecedores import roteador_fornecedores
from app.rotas.rotas_operacoes import roteador_operacoes
from app.rotas.rotas_orcamentos import roteador_orcamentos
from app.rotas.rotas_pagamentos import roteador_pagamentos
from app.rotas.rotas_relatorios import roteador_relatorios
from app.rotas.rotas_usuarios import roteador_usuarios
from app.rotas.rotas_vendas import roteador_vendas


configurar_logs()
logger = logging.getLogger("novaris.api")


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    if configuracoes.executar_migracoes_inicio:
        logger.info("inicializacao_banco iniciada")
        BaseModelo.metadata.create_all(motor_banco)
        aplicar_migracoes_leves()
        logger.info("inicializacao_banco concluida")
    logger.info(
        "aplicacao iniciada ambiente=%s versao=%s",
        configuracoes.ambiente,
        configuracoes.versao_aplicacao,
    )
    yield
    motor_banco.dispose()
    logger.info("aplicacao encerrada")


aplicacao = FastAPI(
    title=configuracoes.nome_aplicacao,
    version=configuracoes.versao_aplicacao,
    description="SaaS multiempresa Novaris One.",
    lifespan=ciclo_de_vida,
    docs_url="/docs" if configuracoes.habilitar_documentacao else None,
    redoc_url="/redoc" if configuracoes.habilitar_documentacao else None,
    openapi_url=(
        "/openapi.json" if configuracoes.habilitar_documentacao else None
    ),
)

aplicacao.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=configuracoes.hosts_permitidos,
)
aplicacao.add_middleware(
    CORSMiddleware,
    allow_origins=configuracoes.origens_cors,
    allow_origin_regex=configuracoes.regex_origens_cors,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)


@aplicacao.middleware("http")
async def registrar_requisicao(requisicao: Request, chamar_proxima):
    inicio = time.perf_counter()
    request_id = requisicao.headers.get("x-request-id") or uuid4().hex
    requisicao.state.request_id = request_id
    try:
        resposta = await chamar_proxima(requisicao)
    except Exception:
        logger.exception(
            "erro_critico request_id=%s metodo=%s rota=%s",
            request_id,
            requisicao.method,
            requisicao.url.path,
        )
        raise
    duracao_ms = (time.perf_counter() - inicio) * 1000
    resposta.headers["X-Request-ID"] = request_id
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["Referrer-Policy"] = "no-referrer"
    resposta.headers["Permissions-Policy"] = "camera=(), microphone=()"
    if configuracoes.producao:
        resposta.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    if requisicao.url.path != "/health":
        logger.info(
            "http request_id=%s metodo=%s rota=%s status=%s duracao_ms=%.2f",
            request_id,
            requisicao.method,
            requisicao.url.path,
            resposta.status_code,
            duracao_ms,
        )
    return resposta


@aplicacao.exception_handler(RequestValidationError)
async def tratar_validacao(_: Request, erro: RequestValidationError):
    erros = []
    for item in erro.errors():
        seguro = {
            chave: valor
            for chave, valor in item.items()
            if chave not in {"input", "ctx", "url"}
        }
        erros.append(seguro)
    return JSONResponse(status_code=422, content={"detail": erros})


@aplicacao.exception_handler(Exception)
async def tratar_erro_critico(requisicao: Request, _: Exception):
    mensagem = (
        "Ocorreu um erro interno. Informe o codigo da requisicao ao suporte."
        if configuracoes.producao
        else "Ocorreu um erro interno na API."
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": mensagem,
            "request_id": getattr(requisicao.state, "request_id", None),
        },
    )


aplicacao.include_router(roteador_autenticacao)
aplicacao.include_router(roteador_dashboard)
aplicacao.include_router(roteador_estoque)
aplicacao.include_router(roteador_vendas)
aplicacao.include_router(roteador_fornecedores)
aplicacao.include_router(roteador_financeiro)
aplicacao.include_router(roteador_pagamentos)
aplicacao.include_router(roteador_usuarios)
aplicacao.include_router(roteador_caixa)
aplicacao.include_router(roteador_operacoes)
aplicacao.include_router(roteador_relatorios)
aplicacao.include_router(roteador_backup)
aplicacao.include_router(roteador_clientes)
aplicacao.include_router(roteador_compras)
aplicacao.include_router(roteador_orcamentos)


@aplicacao.get("/health", tags=["Sistema"], summary="Verificar saude da API")
def verificar_saude():
    banco = "ok"
    status_api = "ok"
    codigo = 200
    try:
        with motor_banco.connect() as conexao:
            conexao.execute(text("SELECT 1"))
    except Exception:
        logger.exception("health_check banco_indisponivel")
        banco = "indisponivel"
        status_api = "degradado"
        codigo = 503
    return JSONResponse(
        status_code=codigo,
        content={
            "status_api": status_api,
            "status_banco": banco,
            "versao": configuracoes.versao_aplicacao,
            "ambiente": configuracoes.ambiente,
            "data_hora_servidor": datetime.now(timezone.utc).isoformat(),
        },
    )


# O nome "app" e mantido porque o Uvicorn procura app.main:app.
app = aplicacao
