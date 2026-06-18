from fastapi import HTTPException
from datetime import date, datetime, time, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.esquemas.estoque import (
    MovimentacaoCriacao,
    ProdutoAtualizacao,
    ProdutoCriacao,
)
from app.modelos.produto import MovimentacaoEstoque, Produto
from app.modelos.fornecedor import Fornecedor
from app.modelos.usuario import Usuario
from app.servicos.servico_auditoria import registrar_auditoria


def listar_produtos_empresa(
    usuario: Usuario,
    sessao: Session,
) -> list[Produto]:
    """Lista somente os produtos da empresa do usuário logado."""
    return list(
        sessao.scalars(
            select(Produto)
            .where(
                Produto.empresa_id == usuario.empresa_id,
                Produto.ativo.is_(True),
            )
            .order_by(Produto.nome)
        ).all()
    )


def cadastrar_produto(
    dados: ProdutoCriacao,
    usuario: Usuario,
    sessao: Session,
) -> Produto:
    """Cadastra um produto e impede código de barras duplicado."""
    produto_existente = sessao.scalar(
        select(Produto).where(
            Produto.empresa_id == usuario.empresa_id,
            Produto.codigo_barras == dados.codigo_barras.strip(),
        )
    )
    if produto_existente:
        raise HTTPException(
            status_code=409,
            detail="Já existe um produto com este código de barras.",
        )

    validar_fornecedor(dados.fornecedor_id, usuario, sessao)
    produto = Produto(
        empresa_id=usuario.empresa_id,
        codigo_barras=dados.codigo_barras.strip(),
        nome=dados.nome.strip(),
        categoria=dados.categoria.strip(),
        quantidade=dados.quantidade,
        estoque_minimo=dados.estoque_minimo,
        preco=dados.preco,
        preco_compra=dados.preco_compra,
        fornecedor_id=dados.fornecedor_id,
        imagem_url=dados.imagem_url or None,
    )
    sessao.add(produto)
    sessao.flush()

    if dados.quantidade > 0:
        sessao.add(
            MovimentacaoEstoque(
                empresa_id=usuario.empresa_id,
                produto_id=produto.id,
                usuario_id=usuario.id,
                tipo="entrada",
                quantidade=dados.quantidade,
                quantidade_anterior=0,
                quantidade_atual=dados.quantidade,
                nome_produto=produto.nome,
                codigo_barras=produto.codigo_barras,
                nome_usuario=usuario.nome,
                origem="cadastro",
            )
        )

    registrar_auditoria(
        sessao,
        usuario,
        "produto_criado",
        "produto",
        produto.id,
        {"nome": produto.nome, "quantidade": produto.quantidade},
    )
    sessao.commit()
    sessao.refresh(produto)
    return produto


def buscar_produto_empresa(
    produto_id: int,
    usuario: Usuario,
    sessao: Session,
) -> Produto:
    produto = sessao.scalar(
        select(Produto).where(
            Produto.id == produto_id,
            Produto.empresa_id == usuario.empresa_id,
            Produto.ativo.is_(True),
        )
    )
    if not produto:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado.",
        )
    return produto


def atualizar_produto(
    produto_id: int,
    dados: ProdutoAtualizacao,
    usuario: Usuario,
    sessao: Session,
) -> Produto:
    """Atualiza os dados básicos sem alterar o saldo do estoque."""
    produto = buscar_produto_empresa(produto_id, usuario, sessao)

    codigo_em_uso = sessao.scalar(
        select(Produto).where(
            Produto.empresa_id == usuario.empresa_id,
            Produto.codigo_barras == dados.codigo_barras.strip(),
            Produto.id != produto_id,
        )
    )
    if codigo_em_uso:
        raise HTTPException(
            status_code=409,
            detail="Já existe outro produto com este código de barras.",
        )

    validar_fornecedor(dados.fornecedor_id, usuario, sessao)
    produto.codigo_barras = dados.codigo_barras.strip()
    produto.nome = dados.nome.strip()
    produto.categoria = dados.categoria.strip()
    produto.preco = dados.preco
    produto.preco_compra = dados.preco_compra
    produto.fornecedor_id = dados.fornecedor_id
    produto.estoque_minimo = dados.estoque_minimo
    produto.imagem_url = dados.imagem_url or None
    registrar_auditoria(
        sessao,
        usuario,
        "produto_atualizado",
        "produto",
        produto.id,
        {"nome": produto.nome, "codigo_barras": produto.codigo_barras},
    )
    sessao.commit()
    sessao.refresh(produto)
    return produto


def validar_fornecedor(
    fornecedor_id: int | None,
    usuario: Usuario,
    sessao: Session,
) -> None:
    if fornecedor_id is None:
        return
    existe = sessao.scalar(
        select(Fornecedor.id).where(
            Fornecedor.id == fornecedor_id,
            Fornecedor.empresa_id == usuario.empresa_id,
        )
    )
    if not existe:
        raise HTTPException(404, "Fornecedor nao encontrado.")


def movimentar_estoque(
    produto_id: int,
    dados: MovimentacaoCriacao,
    usuario: Usuario,
    sessao: Session,
) -> Produto:
    """Soma entradas e desconta vendas do saldo atual."""
    produto = buscar_produto_empresa(produto_id, usuario, sessao)

    tipo_normalizado = "saida" if dados.tipo == "venda" else dados.tipo
    quantidade_anterior = produto.quantidade

    if tipo_normalizado == "saida":
        if produto.quantidade < dados.quantidade:
            raise HTTPException(
                status_code=422,
                detail="Estoque insuficiente para realizar esta venda.",
            )
        produto.quantidade -= dados.quantidade
    else:
        produto.quantidade += dados.quantidade

    sessao.add(
        MovimentacaoEstoque(
            empresa_id=usuario.empresa_id,
            produto_id=produto.id,
            usuario_id=usuario.id,
            tipo=tipo_normalizado,
            quantidade=dados.quantidade,
            quantidade_anterior=quantidade_anterior,
            quantidade_atual=produto.quantidade,
            nome_produto=produto.nome,
            codigo_barras=produto.codigo_barras,
            nome_usuario=usuario.nome,
            origem="estoque",
        )
    )
    registrar_auditoria(
        sessao,
        usuario,
        "estoque_entrada" if tipo_normalizado == "entrada" else "estoque_saida",
        "produto",
        produto.id,
        {
            "quantidade": dados.quantidade,
            "quantidade_anterior": quantidade_anterior,
            "quantidade_atual": produto.quantidade,
        },
    )
    sessao.commit()
    sessao.refresh(produto)
    return produto


def excluir_produto(
    produto_id: int,
    usuario: Usuario,
    sessao: Session,
) -> None:
    produto = buscar_produto_empresa(produto_id, usuario, sessao)
    produto.ativo = False
    registrar_auditoria(
        sessao,
        usuario,
        "produto_excluido",
        "produto",
        produto.id,
        {"nome": produto.nome},
    )
    sessao.commit()


def listar_movimentacoes(
    usuario: Usuario,
    sessao: Session,
    busca: str = "",
    tipo: str | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
) -> list[MovimentacaoEstoque]:
    consulta = select(MovimentacaoEstoque).where(
        MovimentacaoEstoque.empresa_id == usuario.empresa_id
    )

    if busca:
        termo = f"%{busca.strip()}%"
        consulta = consulta.where(
            or_(
                MovimentacaoEstoque.nome_produto.ilike(termo),
                MovimentacaoEstoque.codigo_barras.ilike(termo),
            )
        )
    if tipo:
        consulta = consulta.where(MovimentacaoEstoque.tipo == tipo)
    if data_inicial:
        consulta = consulta.where(
            MovimentacaoEstoque.data_movimentacao
            >= datetime.combine(data_inicial, time.min)
        )
    if data_final:
        limite_final = datetime.combine(data_final, time.min) + timedelta(days=1)
        consulta = consulta.where(
            MovimentacaoEstoque.data_movimentacao < limite_final
        )

    return list(
        sessao.scalars(
            consulta.order_by(
                MovimentacaoEstoque.data_movimentacao.desc()
            )
        ).all()
    )


def listar_alertas_estoque(
    usuario: Usuario,
    sessao: Session,
) -> list[dict]:
    produtos = sessao.scalars(
        select(Produto)
        .where(
            Produto.empresa_id == usuario.empresa_id,
            Produto.ativo.is_(True),
            Produto.quantidade <= Produto.estoque_minimo,
        )
        .order_by(Produto.quantidade, Produto.nome)
    ).all()

    return [
        {
            "produto_id": produto.id,
            "nome": produto.nome,
            "codigo_barras": produto.codigo_barras,
            "quantidade": produto.quantidade,
            "estoque_minimo": produto.estoque_minimo,
            "quantidade_faltante": max(
                produto.estoque_minimo - produto.quantidade,
                0,
            ),
        }
        for produto in produtos
    ]
