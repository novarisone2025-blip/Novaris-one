import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.autenticacao.seguranca import (
    criar_token_acesso,
    criar_token_refresh,
    criptografar_senha,
    decodificar_token,
    verificar_senha,
)
from app.configuracao.configuracoes import configuracoes
from app.esquemas.autenticacao import DadosCadastro, DadosLogin
from app.modelos.empresa import Empresa
from app.modelos.sessao import SessaoRefresh
from app.modelos.usuario import Usuario
from app.servicos.servico_permissoes import (
    TODAS_PERMISSOES,
    serializar_permissoes,
)


logger = logging.getLogger("novaris.autenticacao")


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _emitir_tokens(
    usuario: Usuario,
    sessao: Session,
) -> tuple[dict, str]:
    token_acesso = criar_token_acesso(usuario)
    token_refresh, jti, expiracao = criar_token_refresh(usuario)
    sessao.add(
        SessaoRefresh(
            jti=jti,
            empresa_id=usuario.empresa_id,
            usuario_id=usuario.id,
            expiracao=expiracao,
        )
    )
    return (
        {
            "token_acesso": token_acesso,
            "tipo_token": "bearer",
            "expira_em_segundos": configuracoes.minutos_token * 60,
        },
        token_refresh,
    )


def cadastrar_usuario_com_empresa(
    dados: DadosCadastro,
    sessao: Session,
) -> tuple[dict, str]:
    """Cadastra a empresa e seu primeiro usuario administrador."""
    email_normalizado = dados.email.lower()
    usuario_existente = sessao.scalar(
        select(Usuario).where(Usuario.email == email_normalizado)
    )
    if usuario_existente:
        raise HTTPException(
            status_code=409,
            detail="Este e-mail ja esta cadastrado.",
        )

    empresa = Empresa(
        nome=dados.nome_empresa,
        cnpj=dados.cnpj,
        telefone=dados.telefone_empresa,
    )
    sessao.add(empresa)
    sessao.flush()

    usuario = Usuario(
        nome=dados.nome_usuario,
        email=email_normalizado,
        senha_criptografada=criptografar_senha(dados.senha),
        empresa_id=empresa.id,
        tipo_usuario="admin",
        cargo="Administrador",
        permissoes=serializar_permissoes(TODAS_PERMISSOES),
    )
    sessao.add(usuario)
    sessao.flush()
    resposta, refresh = _emitir_tokens(usuario, sessao)
    sessao.commit()
    logger.info(
        "cadastro_empresa concluido empresa_id=%s usuario_id=%s",
        empresa.id,
        usuario.id,
    )
    return resposta, refresh


def autenticar_usuario(
    dados: DadosLogin,
    sessao: Session,
) -> tuple[dict, str]:
    """Verifica e-mail e senha e cria uma sessao renovavel."""
    usuario = sessao.scalar(
        select(Usuario).where(Usuario.email == dados.email.lower())
    )
    if not usuario or not verificar_senha(
        dados.senha,
        usuario.senha_criptografada,
    ):
        logger.warning("login recusado motivo=credenciais_invalidas")
        raise HTTPException(
            status_code=401,
            detail="E-mail ou senha invalidos.",
        )
    if not usuario.ativo:
        logger.warning("login recusado usuario_id=%s motivo=inativo", usuario.id)
        raise HTTPException(
            status_code=403,
            detail="Este usuario esta desativado.",
        )

    resposta, refresh = _emitir_tokens(usuario, sessao)
    sessao.commit()
    logger.info(
        "login concluido empresa_id=%s usuario_id=%s",
        usuario.empresa_id,
        usuario.id,
    )
    return resposta, refresh


def renovar_sessao(
    token_refresh: str,
    sessao: Session,
) -> tuple[dict, str]:
    dados = decodificar_token(token_refresh, "refresh")
    agora = _agora()
    registro = sessao.scalar(
        select(SessaoRefresh)
        .where(
            SessaoRefresh.jti == dados["jti"],
            SessaoRefresh.usuario_id == int(dados["sub"]),
            SessaoRefresh.empresa_id == int(dados["empresa_id"]),
            SessaoRefresh.revogado.is_(False),
        )
        .with_for_update()
    )
    if not registro or registro.expiracao <= agora:
        raise HTTPException(401, "Sessao de renovacao invalida ou expirada.")
    usuario = sessao.scalar(
        select(Usuario).where(
            Usuario.id == registro.usuario_id,
            Usuario.empresa_id == registro.empresa_id,
            Usuario.ativo.is_(True),
        )
    )
    if not usuario:
        raise HTTPException(401, "Usuario inativo ou inexistente.")

    registro.revogado = True
    registro.usado_em = agora
    registro.revogado_em = agora
    resposta, novo_refresh = _emitir_tokens(usuario, sessao)
    sessao.commit()
    logger.info(
        "sessao renovada empresa_id=%s usuario_id=%s",
        usuario.empresa_id,
        usuario.id,
    )
    return resposta, novo_refresh


def revogar_sessao(token_refresh: str | None, sessao: Session) -> None:
    if not token_refresh:
        return
    try:
        dados = decodificar_token(token_refresh, "refresh")
    except HTTPException:
        return
    agora = _agora()
    sessao.execute(
        update(SessaoRefresh)
        .where(
            SessaoRefresh.jti == dados["jti"],
            SessaoRefresh.revogado.is_(False),
        )
        .values(revogado=True, revogado_em=agora)
    )
    sessao.commit()
    logger.info(
        "logout concluido empresa_id=%s usuario_id=%s",
        dados.get("empresa_id"),
        dados.get("sub"),
    )
