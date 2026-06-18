from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.esquemas.fornecedor import FornecedorCriacao
from app.modelos.fornecedor import Fornecedor
from app.modelos.produto import Produto
from app.modelos.usuario import Usuario


def listar_fornecedores(usuario: Usuario, sessao: Session) -> list[dict]:
    linhas = sessao.execute(
        select(
            Fornecedor,
            func.count(Produto.id).label("total_produtos"),
        )
        .outerjoin(
            Produto,
            (Produto.fornecedor_id == Fornecedor.id)
            & (Produto.empresa_id == Fornecedor.empresa_id),
        )
        .where(Fornecedor.empresa_id == usuario.empresa_id)
        .group_by(Fornecedor.id)
        .order_by(Fornecedor.nome)
    ).all()
    return [
        {
            "id": fornecedor.id,
            "nome": fornecedor.nome,
            "cnpj": fornecedor.cnpj,
            "telefone": fornecedor.telefone,
            "email": fornecedor.email,
            "contato": fornecedor.contato,
            "data_criacao": fornecedor.data_criacao,
            "total_produtos": total,
        }
        for fornecedor, total in linhas
    ]


def buscar_fornecedor(
    fornecedor_id: int,
    usuario: Usuario,
    sessao: Session,
) -> Fornecedor:
    fornecedor = sessao.scalar(
        select(Fornecedor).where(
            Fornecedor.id == fornecedor_id,
            Fornecedor.empresa_id == usuario.empresa_id,
        )
    )
    if not fornecedor:
        raise HTTPException(404, "Fornecedor nao encontrado.")
    return fornecedor


def salvar_fornecedor(
    dados: FornecedorCriacao,
    usuario: Usuario,
    sessao: Session,
    fornecedor_id: int | None = None,
) -> Fornecedor:
    duplicado = sessao.scalar(
        select(Fornecedor).where(
            Fornecedor.empresa_id == usuario.empresa_id,
            func.lower(Fornecedor.nome) == dados.nome.strip().lower(),
            *(
                [Fornecedor.id != fornecedor_id]
                if fornecedor_id is not None
                else []
            ),
        )
    )
    if duplicado:
        raise HTTPException(409, "Ja existe um fornecedor com este nome.")

    fornecedor = (
        buscar_fornecedor(fornecedor_id, usuario, sessao)
        if fornecedor_id
        else Fornecedor(empresa_id=usuario.empresa_id)
    )
    fornecedor.nome = dados.nome.strip()
    fornecedor.cnpj = dados.cnpj or None
    fornecedor.telefone = dados.telefone or None
    fornecedor.email = str(dados.email) if dados.email else None
    fornecedor.contato = dados.contato or None
    sessao.add(fornecedor)
    sessao.commit()
    sessao.refresh(fornecedor)
    return fornecedor


def excluir_fornecedor(
    fornecedor_id: int,
    usuario: Usuario,
    sessao: Session,
) -> None:
    fornecedor = buscar_fornecedor(fornecedor_id, usuario, sessao)
    produtos = sessao.scalars(
        select(Produto).where(
            Produto.fornecedor_id == fornecedor.id,
            Produto.empresa_id == usuario.empresa_id,
        )
    ).all()
    for produto in produtos:
        produto.fornecedor_id = None
    sessao.delete(fornecedor)
    sessao.commit()
