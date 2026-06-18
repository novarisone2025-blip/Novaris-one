import re

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.autenticacao.seguranca import obter_usuario_logado
from app.banco.conexao import obter_sessao_banco
from app.configuracao.configuracoes import configuracoes
from app.esquemas.autenticacao import (
    DadosCadastro,
    DadosLogin,
    RespostaLogout,
    RespostaToken,
)
from app.esquemas.usuario import UsuarioResposta
from app.modelos.usuario import Usuario
from app.servicos.servico_autenticacao import (
    autenticar_usuario,
    cadastrar_usuario_com_empresa,
    renovar_sessao,
    revogar_sessao,
)
from app.servicos.servico_permissoes import permissoes_do_usuario


roteador_autenticacao = APIRouter(
    prefix="/auth",
    tags=["Autenticacao"],
)


def _salvar_cookie_refresh(resposta: Response, token: str) -> None:
    resposta.set_cookie(
        key=configuracoes.nome_cookie_refresh,
        value=token,
        max_age=configuracoes.dias_refresh_token * 24 * 60 * 60,
        httponly=True,
        secure=configuracoes.cookie_seguro,
        samesite="lax",
        domain=configuracoes.dominio_cookie,
        path="/auth",
    )


def _remover_cookie_refresh(resposta: Response) -> None:
    resposta.delete_cookie(
        key=configuracoes.nome_cookie_refresh,
        domain=configuracoes.dominio_cookie,
        path="/auth",
        httponly=True,
        secure=configuracoes.cookie_seguro,
        samesite="lax",
    )


def _validar_origem(requisicao: Request) -> None:
    origem = requisicao.headers.get("origin")
    if not origem:
        return
    if requisicao.headers.get("x-requested-with") != "XMLHttpRequest":
        raise HTTPException(403, "Cabecalho de seguranca ausente.")
    origem = origem.rstrip("/")
    if origem in configuracoes.origens_cors:
        return
    if re.fullmatch(configuracoes.regex_origens_cors, origem):
        return
    raise HTTPException(403, "Origem nao autorizada.")


@roteador_autenticacao.post(
    "/register",
    response_model=RespostaToken,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar empresa e usuario",
)
def cadastrar(
    dados: DadosCadastro,
    resposta_http: Response,
    sessao: Session = Depends(obter_sessao_banco),
):
    resposta, refresh = cadastrar_usuario_com_empresa(dados, sessao)
    _salvar_cookie_refresh(resposta_http, refresh)
    return resposta


@roteador_autenticacao.post(
    "/login",
    response_model=RespostaToken,
    summary="Entrar no sistema",
)
def entrar(
    dados: DadosLogin,
    resposta_http: Response,
    sessao: Session = Depends(obter_sessao_banco),
):
    resposta, refresh = autenticar_usuario(dados, sessao)
    _salvar_cookie_refresh(resposta_http, refresh)
    return resposta


@roteador_autenticacao.post(
    "/refresh",
    response_model=RespostaToken,
    summary="Renovar sessao",
)
def atualizar_token(
    requisicao: Request,
    resposta_http: Response,
    sessao: Session = Depends(obter_sessao_banco),
):
    _validar_origem(requisicao)
    token = requisicao.cookies.get(configuracoes.nome_cookie_refresh)
    if not token:
        raise HTTPException(401, "Sessao de renovacao nao encontrada.")
    resposta, refresh = renovar_sessao(token, sessao)
    _salvar_cookie_refresh(resposta_http, refresh)
    return resposta


@roteador_autenticacao.post(
    "/logout",
    response_model=RespostaLogout,
    summary="Encerrar sessao",
)
def sair(
    requisicao: Request,
    resposta_http: Response,
    sessao: Session = Depends(obter_sessao_banco),
):
    _validar_origem(requisicao)
    revogar_sessao(
        requisicao.cookies.get(configuracoes.nome_cookie_refresh),
        sessao,
    )
    _remover_cookie_refresh(resposta_http)
    return RespostaLogout()


@roteador_autenticacao.get(
    "/me",
    response_model=UsuarioResposta,
    summary="Consultar usuario logado",
)
def consultar_usuario_logado(
    usuario: Usuario = Depends(obter_usuario_logado),
):
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "tipo_usuario": usuario.tipo_usuario,
        "cargo": usuario.cargo,
        "permissoes": permissoes_do_usuario(usuario),
        "ativo": usuario.ativo,
        "data_cadastro": usuario.data_cadastro,
        "empresa": usuario.empresa,
    }
