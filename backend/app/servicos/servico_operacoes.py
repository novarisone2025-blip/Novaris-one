from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.esquemas.operacoes import DevolucaoVendaCriacao
from app.modelos.operacoes import DevolucaoVenda, ItemDevolucaoVenda
from app.modelos.produto import MovimentacaoEstoque, Produto
from app.modelos.usuario import Usuario
from app.modelos.venda import ItemVenda, Venda
from app.servicos.servico_auditoria import registrar_auditoria
from app.servicos.servico_caixa import exigir_caixa_aberto


CENTAVOS = Decimal("0.01")


def _dinheiro(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def _quantidades_ja_devolvidas(
    venda_id: int,
    empresa_id: int,
    sessao: Session,
) -> dict[int, int]:
    linhas = sessao.execute(
        select(
            ItemDevolucaoVenda.item_venda_id,
            func.sum(ItemDevolucaoVenda.quantidade),
        )
        .join(
            DevolucaoVenda,
            DevolucaoVenda.id == ItemDevolucaoVenda.devolucao_id,
        )
        .where(
            DevolucaoVenda.empresa_id == empresa_id,
            DevolucaoVenda.venda_id == venda_id,
            ItemDevolucaoVenda.direcao == "devolvido",
        )
        .group_by(ItemDevolucaoVenda.item_venda_id)
    ).all()
    return {item_id: int(quantidade) for item_id, quantidade in linhas}


def detalhar_venda_para_devolucao(
    venda_id: int,
    usuario: Usuario,
    sessao: Session,
) -> dict:
    venda = sessao.scalar(
        select(Venda)
        .options(selectinload(Venda.itens))
        .where(
            Venda.id == venda_id,
            Venda.empresa_id == usuario.empresa_id,
        )
    )
    if not venda:
        raise HTTPException(404, "Venda nao encontrada.")
    if venda.status != "pago":
        raise HTTPException(409, "Somente vendas pagas aceitam devolucao.")
    autor = sessao.scalar(
        select(Usuario).where(
            Usuario.id == venda.usuario_id,
            Usuario.empresa_id == usuario.empresa_id,
        )
    )
    devolvidas = _quantidades_ja_devolvidas(venda.id, usuario.empresa_id, sessao)
    return {
        "id": venda.id,
        "status": venda.status,
        "forma_pagamento": venda.forma_pagamento,
        "valor_total": venda.valor_total,
        "data_venda": venda.data_venda,
        "nome_usuario": autor.nome,
        "itens": [
            {
                "id": item.id,
                "produto_id": item.produto_id,
                "nome_produto": item.nome_produto,
                "codigo_barras": item.codigo_barras,
                "quantidade_vendida": item.quantidade,
                "quantidade_ja_devolvida": devolvidas.get(item.id, 0),
                "quantidade_disponivel_devolucao": (
                    item.quantidade - devolvidas.get(item.id, 0)
                ),
                "valor_unitario": item.valor_unitario,
            }
            for item in venda.itens
        ],
    }


def _serializar_operacao(
    operacao: DevolucaoVenda,
    nome_usuario: str,
) -> dict:
    return {
        "id": operacao.id,
        "venda_id": operacao.venda_id,
        "tipo": operacao.tipo,
        "motivo": operacao.motivo,
        "credito_devolvido": operacao.credito_devolvido,
        "valor_novos_itens": operacao.valor_novos_itens,
        "valor_estornado": operacao.valor_estornado,
        "valor_adicional": operacao.valor_adicional,
        "forma_pagamento": operacao.forma_pagamento,
        "usuario_id": operacao.usuario_id,
        "nome_usuario": nome_usuario,
        "caixa_id": operacao.caixa_id,
        "data_operacao": operacao.data_operacao,
        "itens": [
            {
                "produto_id": item.produto_id,
                "nome_produto": item.nome_produto,
                "codigo_barras": item.codigo_barras,
                "direcao": item.direcao,
                "quantidade": item.quantidade,
                "valor_unitario": item.valor_unitario,
            }
            for item in operacao.itens
        ],
    }


def registrar_devolucao_ou_troca(
    venda_id: int,
    dados: DevolucaoVendaCriacao,
    usuario: Usuario,
    sessao: Session,
) -> dict:
    caixa = exigir_caixa_aberto(usuario, sessao)
    venda = sessao.scalar(
        select(Venda)
        .options(selectinload(Venda.itens))
        .where(
            Venda.id == venda_id,
            Venda.empresa_id == usuario.empresa_id,
        )
        .with_for_update()
    )
    if not venda:
        raise HTTPException(404, "Venda nao encontrada.")
    if venda.status != "pago":
        raise HTTPException(409, "Somente vendas pagas aceitam esta operacao.")

    itens_venda = {item.id: item for item in venda.itens}
    devolvidas = _quantidades_ja_devolvidas(venda.id, usuario.empresa_id, sessao)
    quantidades_solicitadas = defaultdict(int)
    for item in dados.itens_devolvidos:
        quantidades_solicitadas[item.item_venda_id] += item.quantidade
    for item_id, quantidade in quantidades_solicitadas.items():
        item_venda = itens_venda.get(item_id)
        if not item_venda:
            raise HTTPException(404, "Item nao pertence a esta venda.")
        disponivel = item_venda.quantidade - devolvidas.get(item_id, 0)
        if quantidade > disponivel:
            raise HTTPException(
                422,
                f"Quantidade devolvida excede o saldo de {item_venda.nome_produto}.",
            )

    produtos_ids = {itens_venda[item_id].produto_id for item_id in quantidades_solicitadas}
    novos_por_codigo = defaultdict(int)
    for item in dados.itens_novos:
        novos_por_codigo[item.codigo_barras.strip()] += item.quantidade
    consulta_produtos = select(Produto).where(
        Produto.empresa_id == usuario.empresa_id,
        (
            Produto.id.in_(produtos_ids)
            if produtos_ids
            else Produto.id == -1
        )
        | (
            Produto.codigo_barras.in_(novos_por_codigo.keys())
            if novos_por_codigo
            else Produto.id == -1
        ),
    ).with_for_update()
    produtos = list(sessao.scalars(consulta_produtos).all())
    produtos_id = {produto.id: produto for produto in produtos}
    produtos_codigo = {produto.codigo_barras: produto for produto in produtos}
    if any(item.produto_id not in produtos_id for item in itens_venda.values() if item.id in quantidades_solicitadas):
        raise HTTPException(409, "Produto original da venda nao foi localizado.")
    for codigo, quantidade in novos_por_codigo.items():
        produto = produtos_codigo.get(codigo)
        if not produto or not produto.ativo:
            raise HTTPException(404, f"Produto novo nao encontrado: {codigo}.")
        if produto.quantidade < quantidade:
            raise HTTPException(
                422,
                f"Estoque insuficiente para {produto.nome}. Disponivel: {produto.quantidade}.",
            )

    fator_desconto = (
        Decimal(venda.valor_total) / Decimal(venda.subtotal)
        if venda.subtotal
        else Decimal("0")
    )
    credito = Decimal("0")
    for item_id, quantidade in quantidades_solicitadas.items():
        item = itens_venda[item_id]
        credito += Decimal(item.valor_unitario) * quantidade * fator_desconto
    credito = _dinheiro(credito)
    valor_novos = _dinheiro(sum(
        Decimal(produtos_codigo[codigo].preco) * quantidade
        for codigo, quantidade in novos_por_codigo.items()
    ))
    valor_estornado = _dinheiro(max(credito - valor_novos, Decimal("0")))
    valor_adicional = _dinheiro(max(valor_novos - credito, Decimal("0")))
    forma_pagamento = dados.forma_pagamento or venda.forma_pagamento

    operacao = DevolucaoVenda(
        empresa_id=usuario.empresa_id,
        venda_id=venda.id,
        usuario_id=usuario.id,
        caixa_id=caixa.id,
        tipo=dados.tipo,
        motivo=dados.motivo.strip(),
        credito_devolvido=credito,
        valor_novos_itens=valor_novos,
        valor_estornado=valor_estornado,
        valor_adicional=valor_adicional,
        forma_pagamento=forma_pagamento,
    )
    sessao.add(operacao)
    sessao.flush()

    for item_id, quantidade in quantidades_solicitadas.items():
        item = itens_venda[item_id]
        produto = produtos_id[item.produto_id]
        anterior = produto.quantidade
        produto.quantidade += quantidade
        sessao.add(ItemDevolucaoVenda(
            empresa_id=usuario.empresa_id,
            devolucao_id=operacao.id,
            item_venda_id=item.id,
            produto_id=produto.id,
            direcao="devolvido",
            nome_produto=item.nome_produto,
            codigo_barras=item.codigo_barras,
            quantidade=quantidade,
            valor_unitario=item.valor_unitario,
            custo_unitario=item.custo_unitario,
        ))
        sessao.add(MovimentacaoEstoque(
            empresa_id=usuario.empresa_id,
            produto_id=produto.id,
            usuario_id=usuario.id,
            venda_id=venda.id,
            tipo="entrada",
            quantidade=quantidade,
            quantidade_anterior=anterior,
            quantidade_atual=produto.quantidade,
            nome_produto=produto.nome,
            codigo_barras=produto.codigo_barras,
            nome_usuario=usuario.nome,
            origem=dados.tipo,
        ))

    for codigo, quantidade in novos_por_codigo.items():
        produto = produtos_codigo[codigo]
        anterior = produto.quantidade
        produto.quantidade -= quantidade
        sessao.add(ItemDevolucaoVenda(
            empresa_id=usuario.empresa_id,
            devolucao_id=operacao.id,
            item_venda_id=None,
            produto_id=produto.id,
            direcao="novo",
            nome_produto=produto.nome,
            codigo_barras=produto.codigo_barras,
            quantidade=quantidade,
            valor_unitario=produto.preco,
            custo_unitario=produto.preco_compra,
        ))
        sessao.add(MovimentacaoEstoque(
            empresa_id=usuario.empresa_id,
            produto_id=produto.id,
            usuario_id=usuario.id,
            venda_id=venda.id,
            tipo="saida",
            quantidade=quantidade,
            quantidade_anterior=anterior,
            quantidade_atual=produto.quantidade,
            nome_produto=produto.nome,
            codigo_barras=produto.codigo_barras,
            nome_usuario=usuario.nome,
            origem="troca",
        ))

    registrar_auditoria(
        sessao,
        usuario,
        "troca_realizada" if dados.tipo == "troca" else "devolucao_realizada",
        "venda",
        venda.id,
        {
            "operacao_id": operacao.id,
            "motivo": operacao.motivo,
            "credito_devolvido": credito,
            "valor_estornado": valor_estornado,
            "valor_adicional": valor_adicional,
        },
    )
    sessao.commit()
    operacao = sessao.scalar(
        select(DevolucaoVenda)
        .options(selectinload(DevolucaoVenda.itens))
        .where(DevolucaoVenda.id == operacao.id)
    )
    return _serializar_operacao(operacao, usuario.nome)


def listar_devolucoes(
    usuario: Usuario,
    sessao: Session,
    venda_id: int | None = None,
) -> list[dict]:
    consulta = (
        select(DevolucaoVenda)
        .options(selectinload(DevolucaoVenda.itens))
        .where(DevolucaoVenda.empresa_id == usuario.empresa_id)
        .order_by(DevolucaoVenda.data_operacao.desc())
    )
    if venda_id:
        consulta = consulta.where(DevolucaoVenda.venda_id == venda_id)
    operacoes = sessao.scalars(consulta).all()
    usuarios = {
        item.id: item.nome
        for item in sessao.scalars(
            select(Usuario).where(Usuario.empresa_id == usuario.empresa_id)
        ).all()
    }
    return [
        _serializar_operacao(operacao, usuarios[operacao.usuario_id])
        for operacao in operacoes
    ]
