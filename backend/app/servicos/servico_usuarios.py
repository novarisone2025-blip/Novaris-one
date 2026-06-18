from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.autenticacao.seguranca import criptografar_senha
from app.esquemas.usuario import (
    UsuarioInternoAtualizacao,
    UsuarioInternoCriacao,
)
from app.modelos.usuario import Usuario
from app.servicos.servico_auditoria import registrar_auditoria
from app.servicos.servico_permissoes import (
    normalizar_permissoes_cargo,
    permissoes_do_usuario,
    serializar_permissoes,
)


def resposta_usuario(usuario: Usuario) -> dict:
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "tipo_usuario": usuario.tipo_usuario,
        "cargo": usuario.cargo,
        "permissoes": permissoes_do_usuario(usuario),
        "ativo": usuario.ativo,
        "data_cadastro": usuario.data_cadastro,
    }


def listar_usuarios_empresa(
    administrador: Usuario,
    sessao: Session,
) -> list[dict]:
    usuarios = sessao.scalars(
        select(Usuario)
        .where(Usuario.empresa_id == administrador.empresa_id)
        .order_by(Usuario.ativo.desc(), Usuario.nome)
    ).all()
    return [resposta_usuario(usuario) for usuario in usuarios]


def _validar_email(
    email: str,
    sessao: Session,
    usuario_id: int | None = None,
) -> str:
    normalizado = email.lower()
    consulta = select(Usuario.id).where(Usuario.email == normalizado)
    if usuario_id:
        consulta = consulta.where(Usuario.id != usuario_id)
    if sessao.scalar(consulta):
        raise HTTPException(409, "Este e-mail ja esta cadastrado.")
    return normalizado


def criar_usuario_interno(
    dados: UsuarioInternoCriacao,
    administrador: Usuario,
    sessao: Session,
) -> Usuario:
    usuario = Usuario(
        empresa_id=administrador.empresa_id,
        nome=dados.nome.strip(),
        email=_validar_email(str(dados.email), sessao),
        senha_criptografada=criptografar_senha(dados.senha),
        tipo_usuario="comum",
        cargo=dados.cargo.strip(),
        permissoes=serializar_permissoes(
            normalizar_permissoes_cargo(dados.permissoes, dados.cargo)
        ),
        ativo=True,
    )
    sessao.add(usuario)
    sessao.flush()
    registrar_auditoria(
        sessao,
        administrador,
        "usuario_criado",
        "usuario",
        usuario.id,
        {"nome": usuario.nome, "cargo": usuario.cargo},
    )
    sessao.commit()
    sessao.refresh(usuario)
    return usuario


def buscar_usuario_empresa(
    usuario_id: int,
    administrador: Usuario,
    sessao: Session,
) -> Usuario:
    usuario = sessao.scalar(
        select(Usuario).where(
            Usuario.id == usuario_id,
            Usuario.empresa_id == administrador.empresa_id,
        )
    )
    if not usuario:
        raise HTTPException(404, "Usuario nao encontrado.")
    return usuario


def atualizar_usuario_interno(
    usuario_id: int,
    dados: UsuarioInternoAtualizacao,
    administrador: Usuario,
    sessao: Session,
) -> Usuario:
    usuario = buscar_usuario_empresa(usuario_id, administrador, sessao)
    if usuario.tipo_usuario == "admin" and usuario.id != administrador.id:
        raise HTTPException(403, "A conta principal nao pode ser alterada.")
    if usuario.id == administrador.id and not dados.ativo:
        raise HTTPException(422, "Voce nao pode desativar seu proprio usuario.")

    usuario.nome = dados.nome.strip()
    usuario.email = _validar_email(
        str(dados.email),
        sessao,
        usuario.id,
    )
    usuario.cargo = dados.cargo.strip()
    usuario.permissoes = serializar_permissoes(
        normalizar_permissoes_cargo(dados.permissoes, dados.cargo)
    )
    usuario.ativo = dados.ativo
    if dados.nova_senha:
        usuario.senha_criptografada = criptografar_senha(dados.nova_senha)
    registrar_auditoria(
        sessao,
        administrador,
        "usuario_atualizado",
        "usuario",
        usuario.id,
        {
            "nome": usuario.nome,
            "cargo": usuario.cargo,
            "ativo": usuario.ativo,
        },
    )
    sessao.commit()
    sessao.refresh(usuario)
    return usuario
