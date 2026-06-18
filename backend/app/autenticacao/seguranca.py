from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.banco.conexao import obter_sessao_banco
from app.configuracao.configuracoes import configuracoes
from app.modelos.usuario import Usuario


contexto_senha = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

esquema_token = OAuth2PasswordBearer(tokenUrl="/auth/login")


def criptografar_senha(senha: str) -> str:
    """Converte a senha digitada em um hash seguro."""
    return contexto_senha.hash(senha)


def verificar_senha(senha_digitada: str, senha_salva: str) -> bool:
    """Compara a senha digitada com o hash salvo no banco."""
    return contexto_senha.verify(senha_digitada, senha_salva)


def _criar_token(
    usuario: Usuario,
    tipo: str,
    validade: timedelta,
) -> tuple[str, str, datetime]:
    agora = datetime.now(timezone.utc)
    expiracao = agora + validade
    jti = uuid4().hex
    conteudo = {
        "sub": str(usuario.id),
        "empresa_id": usuario.empresa_id,
        "tipo": tipo,
        "jti": jti,
        "iat": agora,
        "nbf": agora,
        "exp": expiracao,
        "iss": configuracoes.emissor_jwt,
        "aud": configuracoes.audiencia_jwt,
    }
    token = jwt.encode(
        conteudo,
        configuracoes.chave_secreta,
        algorithm=configuracoes.algoritmo_jwt,
    )
    return token, jti, expiracao.replace(tzinfo=None)


def criar_token_acesso(usuario: Usuario) -> str:
    token, _, _ = _criar_token(
        usuario,
        "access",
        timedelta(minutes=configuracoes.minutos_token),
    )
    return token


def criar_token_refresh(usuario: Usuario) -> tuple[str, str, datetime]:
    return _criar_token(
        usuario,
        "refresh",
        timedelta(days=configuracoes.dias_refresh_token),
    )


def decodificar_token(token: str, tipo_esperado: str) -> dict:
    erro_credencial = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessao invalida ou expirada.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        dados = jwt.decode(
            token,
            configuracoes.chave_secreta,
            algorithms=[configuracoes.algoritmo_jwt],
            audience=configuracoes.audiencia_jwt,
            issuer=configuracoes.emissor_jwt,
        )
        if dados.get("tipo") != tipo_esperado:
            raise erro_credencial
        int(dados.get("sub", 0))
        int(dados.get("empresa_id", 0))
        if not dados.get("jti"):
            raise erro_credencial
        return dados
    except HTTPException:
        raise
    except (jwt.PyJWTError, TypeError, ValueError) as erro:
        raise erro_credencial from erro


def obter_usuario_logado(
    token: str = Depends(esquema_token),
    sessao: Session = Depends(obter_sessao_banco),
) -> Usuario:
    """Valida o access token e devolve o usuario da requisicao."""
    dados_token = decodificar_token(token, "access")
    usuario = sessao.scalar(
        select(Usuario).where(
            Usuario.id == int(dados_token["sub"]),
            Usuario.empresa_id == int(dados_token["empresa_id"]),
            Usuario.ativo.is_(True),
        )
    )
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessao invalida ou expirada.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return usuario
