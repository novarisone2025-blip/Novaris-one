from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.autenticacao.seguranca import obter_usuario_logado
from app.banco.conexao import obter_sessao_banco
from app.esquemas.auditoria import LogAuditoriaResposta
from app.esquemas.usuario import (
    CatalogoPermissoesResposta,
    UsuarioInternoAtualizacao,
    UsuarioInternoCriacao,
    UsuarioInternoResposta,
    DesempenhoUsuarioResposta,
)
from app.modelos.auditoria import LogAuditoria
from app.modelos.usuario import Usuario
from app.servicos.servico_permissoes import (
    PERMISSOES_DISPONIVEIS,
    PERMISSOES_POR_CARGO,
    garantir_permissao,
)
from app.servicos.servico_usuarios import (
    atualizar_usuario_interno,
    criar_usuario_interno,
    listar_usuarios_empresa,
    resposta_usuario,
)
from app.servicos.servico_desempenho_usuarios import (
    calcular_desempenho_usuarios,
)


roteador_usuarios = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@roteador_usuarios.get(
    "/desempenho",
    response_model=list[DesempenhoUsuarioResposta],
)
def consultar_desempenho(
    usuario_id: int | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "usuarios_gerenciar")
    return calcular_desempenho_usuarios(
        usuario,
        sessao,
        data_inicial,
        data_final,
        usuario_id,
    )


@roteador_usuarios.get(
    "/permissoes",
    response_model=CatalogoPermissoesResposta,
)
def consultar_permissoes(
    usuario: Usuario = Depends(obter_usuario_logado),
):
    garantir_permissao(usuario, "usuarios_gerenciar")
    return {
        "permissoes": PERMISSOES_DISPONIVEIS,
        "predefinicoes_cargos": PERMISSOES_POR_CARGO,
    }


@roteador_usuarios.get("", response_model=list[UsuarioInternoResposta])
def consultar_usuarios(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "usuarios_gerenciar")
    return listar_usuarios_empresa(usuario, sessao)


@roteador_usuarios.post(
    "",
    response_model=UsuarioInternoResposta,
    status_code=status.HTTP_201_CREATED,
)
def cadastrar_usuario(
    dados: UsuarioInternoCriacao,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "usuarios_gerenciar")
    return resposta_usuario(criar_usuario_interno(dados, usuario, sessao))


@roteador_usuarios.put(
    "/{usuario_id}",
    response_model=UsuarioInternoResposta,
)
def editar_usuario(
    usuario_id: int,
    dados: UsuarioInternoAtualizacao,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "usuarios_gerenciar")
    return resposta_usuario(
        atualizar_usuario_interno(usuario_id, dados, usuario, sessao)
    )


@roteador_usuarios.get(
    "/auditoria/logs",
    response_model=list[LogAuditoriaResposta],
)
def consultar_logs(
    usuario_id: int | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    limite: int = Query(default=200, ge=1, le=500),
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "auditoria_visualizar")
    consulta = (
        select(LogAuditoria, Usuario)
        .join(
            Usuario,
            (Usuario.id == LogAuditoria.usuario_id)
            & (Usuario.empresa_id == LogAuditoria.empresa_id),
        )
        .where(LogAuditoria.empresa_id == usuario.empresa_id)
    )
    if usuario_id:
        consulta = consulta.where(LogAuditoria.usuario_id == usuario_id)
    if data_inicial:
        consulta = consulta.where(
            LogAuditoria.data_acao >= datetime.combine(data_inicial, time.min)
        )
    if data_final:
        consulta = consulta.where(
            LogAuditoria.data_acao
            < datetime.combine(data_final, time.min) + timedelta(days=1)
        )
    linhas = sessao.execute(
        consulta.order_by(LogAuditoria.data_acao.desc()).limit(limite)
    ).all()
    return [
        {
            "id": log.id,
            "usuario_id": autor.id,
            "nome_usuario": autor.nome,
            "cargo_usuario": autor.cargo,
            "acao": log.acao,
            "entidade": log.entidade,
            "entidade_id": log.entidade_id,
            "detalhes": log.detalhes,
            "data_acao": log.data_acao,
        }
        for log, autor in linhas
    ]
