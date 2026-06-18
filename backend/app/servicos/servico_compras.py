from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.esquemas.compra import PedidoCompraCriacao
from app.modelos.comercial import ItemPedidoCompra, PedidoCompra
from app.modelos.financeiro import LancamentoFinanceiro
from app.modelos.fornecedor import Fornecedor
from app.modelos.produto import MovimentacaoEstoque, Produto
from app.modelos.usuario import Usuario
from app.servicos.servico_auditoria import registrar_auditoria


def agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def listar_sugestoes_reposicao(
    usuario: Usuario,
    sessao: Session,
) -> list[dict]:
    produtos = sessao.scalars(
        select(Produto)
        .options(selectinload(Produto.fornecedor))
        .where(
            Produto.empresa_id == usuario.empresa_id,
            Produto.ativo.is_(True),
            Produto.quantidade <= Produto.estoque_minimo,
        )
        .order_by(Produto.quantidade, Produto.nome)
    ).all()
    sugestoes = []
    for produto in produtos:
        alvo = max(produto.estoque_minimo * 2, produto.estoque_minimo + 1)
        quantidade = max(alvo - produto.quantidade, 1)
        custo = Decimal(produto.preco_compra)
        sugestoes.append({
            "produto_id": produto.id,
            "nome_produto": produto.nome,
            "codigo_barras": produto.codigo_barras,
            "fornecedor_id": produto.fornecedor_id,
            "nome_fornecedor": (
                produto.fornecedor.nome if produto.fornecedor else "Sem fornecedor"
            ),
            "estoque_atual": produto.quantidade,
            "estoque_minimo": produto.estoque_minimo,
            "quantidade_sugerida": quantidade,
            "custo_unitario": custo,
            "custo_estimado": custo * quantidade,
        })
    return sugestoes


def _serializar_pedido(
    pedido: PedidoCompra,
    usuarios: dict[int, Usuario],
) -> dict:
    return {
        "id": pedido.id,
        "fornecedor_id": pedido.fornecedor_id,
        "nome_fornecedor": pedido.fornecedor.nome,
        "usuario_id": pedido.usuario_id,
        "nome_usuario": usuarios[pedido.usuario_id].nome,
        "usuario_recebimento_id": pedido.usuario_recebimento_id,
        "nome_usuario_recebimento": (
            usuarios[pedido.usuario_recebimento_id].nome
            if pedido.usuario_recebimento_id else None
        ),
        "status": pedido.status,
        "valor_total": pedido.valor_total,
        "observacoes": pedido.observacoes,
        "data_criacao": pedido.data_criacao,
        "data_envio": pedido.data_envio,
        "data_recebimento": pedido.data_recebimento,
        "data_cancelamento": pedido.data_cancelamento,
        "itens": [
            {
                "id": item.id,
                "produto_id": item.produto_id,
                "nome_produto": item.nome_produto,
                "codigo_barras": item.codigo_barras,
                "quantidade": item.quantidade,
                "custo_unitario": item.custo_unitario,
                "valor_total": item.valor_total,
            }
            for item in pedido.itens
        ],
    }


def listar_pedidos(usuario: Usuario, sessao: Session) -> list[dict]:
    pedidos = sessao.scalars(
        select(PedidoCompra)
        .options(
            selectinload(PedidoCompra.itens),
            selectinload(PedidoCompra.fornecedor),
        )
        .where(PedidoCompra.empresa_id == usuario.empresa_id)
        .order_by(PedidoCompra.data_criacao.desc())
    ).all()
    usuarios = {
        item.id: item for item in sessao.scalars(
            select(Usuario).where(Usuario.empresa_id == usuario.empresa_id)
        ).all()
    }
    return [_serializar_pedido(pedido, usuarios) for pedido in pedidos]


def criar_pedido(
    dados: PedidoCompraCriacao,
    usuario: Usuario,
    sessao: Session,
) -> dict:
    fornecedor = sessao.scalar(select(Fornecedor).where(
        Fornecedor.id == dados.fornecedor_id,
        Fornecedor.empresa_id == usuario.empresa_id,
    ))
    if not fornecedor:
        raise HTTPException(404, "Fornecedor nao encontrado.")
    ids = {item.produto_id for item in dados.itens}
    produtos = {
        produto.id: produto for produto in sessao.scalars(
            select(Produto).where(
                Produto.id.in_(ids),
                Produto.empresa_id == usuario.empresa_id,
                Produto.ativo.is_(True),
            )
        ).all()
    }
    if len(produtos) != len(ids):
        raise HTTPException(404, "Um ou mais produtos nao foram encontrados.")
    pedido = PedidoCompra(
        empresa_id=usuario.empresa_id,
        fornecedor_id=fornecedor.id,
        usuario_id=usuario.id,
        observacoes=(dados.observacoes or "").strip() or None,
    )
    sessao.add(pedido)
    sessao.flush()
    total = Decimal("0")
    for dados_item in dados.itens:
        produto = produtos[dados_item.produto_id]
        if produto.fornecedor_id and produto.fornecedor_id != fornecedor.id:
            raise HTTPException(
                422,
                f"O produto {produto.nome} pertence a outro fornecedor.",
            )
        custo = (
            Decimal(dados_item.custo_unitario)
            if dados_item.custo_unitario is not None
            else Decimal(produto.preco_compra)
        )
        valor = custo * dados_item.quantidade
        total += valor
        sessao.add(ItemPedidoCompra(
            empresa_id=usuario.empresa_id,
            pedido_id=pedido.id,
            produto_id=produto.id,
            nome_produto=produto.nome,
            codigo_barras=produto.codigo_barras,
            quantidade=dados_item.quantidade,
            custo_unitario=custo,
            valor_total=valor,
        ))
    pedido.valor_total = total
    registrar_auditoria(
        sessao,
        usuario,
        "pedido_compra_criado",
        "pedido_compra",
        pedido.id,
        {"fornecedor_id": fornecedor.id, "valor_total": total},
    )
    sessao.commit()
    return next(item for item in listar_pedidos(usuario, sessao) if item["id"] == pedido.id)


def atualizar_status_pedido(
    pedido_id: int,
    status: str,
    usuario: Usuario,
    sessao: Session,
) -> dict:
    pedido = sessao.scalar(
        select(PedidoCompra)
        .options(
            selectinload(PedidoCompra.itens),
            selectinload(PedidoCompra.fornecedor),
        )
        .where(
            PedidoCompra.id == pedido_id,
            PedidoCompra.empresa_id == usuario.empresa_id,
        )
        .with_for_update()
    )
    if not pedido:
        raise HTTPException(404, "Pedido de compra nao encontrado.")
    if pedido.status in {"recebido", "cancelado"}:
        raise HTTPException(409, "Este pedido nao pode mais ser alterado.")
    status_anterior = pedido.status
    momento = agora()
    if status == "enviado":
        pedido.status = status
        pedido.data_envio = momento
    elif status == "cancelado":
        pedido.status = status
        pedido.data_cancelamento = momento
    elif status == "recebido":
        produtos = {
            produto.id: produto for produto in sessao.scalars(
                select(Produto).where(
                    Produto.empresa_id == usuario.empresa_id,
                    Produto.id.in_([item.produto_id for item in pedido.itens]),
                ).with_for_update()
            ).all()
        }
        if len(produtos) != len(pedido.itens):
            raise HTTPException(409, "Nao foi possivel localizar todos os produtos.")
        for item in pedido.itens:
            produto = produtos[item.produto_id]
            anterior = produto.quantidade
            produto.quantidade += item.quantidade
            sessao.add(MovimentacaoEstoque(
                empresa_id=usuario.empresa_id,
                produto_id=produto.id,
                usuario_id=usuario.id,
                pedido_compra_id=pedido.id,
                tipo="entrada",
                quantidade=item.quantidade,
                quantidade_anterior=anterior,
                quantidade_atual=produto.quantidade,
                nome_produto=produto.nome,
                codigo_barras=produto.codigo_barras,
                nome_usuario=usuario.nome,
                origem="pedido_compra",
            ))
        if pedido.valor_total > 0:
            sessao.add(LancamentoFinanceiro(
                empresa_id=usuario.empresa_id,
                usuario_id=usuario.id,
                pedido_compra_id=pedido.id,
                tipo="saida",
                categoria="Compras",
                descricao=f"Recebimento do pedido de compra #{pedido.id}",
                valor=pedido.valor_total,
                data_lancamento=momento,
            ))
        pedido.status = status
        pedido.usuario_recebimento_id = usuario.id
        pedido.data_recebimento = momento
    elif status != "pendente":
        raise HTTPException(422, "Status de pedido invalido.")
    else:
        pedido.status = status
    registrar_auditoria(
        sessao,
        usuario,
        f"pedido_compra_{status}",
        "pedido_compra",
        pedido.id,
        {
            "status_anterior": status_anterior,
            "status_atual": pedido.status,
            "valor_total": pedido.valor_total,
        },
    )
    sessao.commit()
    return next(item for item in listar_pedidos(usuario, sessao) if item["id"] == pedido.id)
