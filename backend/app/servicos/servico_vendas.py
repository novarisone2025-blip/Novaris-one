from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import logging
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.esquemas.venda import CancelamentoVendaCriacao, VendaCriacao
from app.modelos.cliente import Cliente
from app.modelos.produto import MovimentacaoEstoque, Produto
from app.modelos.usuario import Usuario
from app.modelos.venda import CancelamentoVenda, ItemVenda, Venda
from app.servicos.servico_gateway_pix import criar_cobranca_pix
from app.servicos.servico_pagamentos import obter_configuracao_modelo
from app.servicos.servico_pix import gerar_qr_code_base64
from app.servicos.servico_auditoria import registrar_auditoria
from app.servicos.servico_caixa import exigir_caixa_aberto
from app.servicos.servico_permissoes import permissoes_do_usuario


logger = logging.getLogger("novaris.vendas")


def buscar_produto_por_codigo(
    codigo_barras: str,
    usuario: Usuario,
    sessao: Session,
) -> Produto:
    produto = sessao.scalar(
        select(Produto).where(
            Produto.empresa_id == usuario.empresa_id,
            Produto.codigo_barras == codigo_barras.strip(),
            Produto.ativo.is_(True),
        )
    )
    if not produto:
        raise HTTPException(404, "Produto nao encontrado pelo codigo de barras.")
    return produto


def buscar_produtos_por_nome(
    nome: str,
    usuario: Usuario,
    sessao: Session,
) -> list[Produto]:
    termo = nome.strip()
    if len(termo) < 2:
        return []
    palavras = [palavra for palavra in termo.split() if palavra]
    filtros = [Produto.nome.ilike(f"%{palavra}%") for palavra in palavras]
    consulta = select(Produto).where(
        Produto.empresa_id == usuario.empresa_id,
        Produto.ativo.is_(True),
        *filtros,
    )
    return list(
        sessao.scalars(
            consulta.order_by(Produto.nome).limit(20)
        ).all()
    )


def _produtos_da_venda(
    quantidades: dict[str, int],
    usuario: Usuario,
    sessao: Session,
    bloquear: bool = False,
) -> dict[str, Produto]:
    consulta = select(Produto).where(
        Produto.empresa_id == usuario.empresa_id,
        Produto.codigo_barras.in_(quantidades.keys()),
        Produto.ativo.is_(True),
    )
    if bloquear:
        consulta = consulta.with_for_update()
    produtos = list(sessao.scalars(consulta).all())
    produtos_por_codigo = {
        produto.codigo_barras: produto for produto in produtos
    }
    ausentes = set(quantidades) - set(produtos_por_codigo)
    if ausentes:
        raise HTTPException(
            404,
            "Produto nao encontrado: " + ", ".join(sorted(ausentes)),
        )
    for codigo, quantidade in quantidades.items():
        produto = produtos_por_codigo[codigo]
        if produto.quantidade < quantidade:
            raise HTTPException(
                422,
                f"Estoque insuficiente para {produto.nome}. "
                f"Disponivel: {produto.quantidade}.",
            )
    return produtos_por_codigo


def _baixar_estoque_venda(
    venda: Venda,
    usuario: Usuario,
    sessao: Session,
) -> list[tuple[ItemVenda, Produto]]:
    quantidades = {
        item.codigo_barras: item.quantidade for item in venda.itens
    }
    produtos = _produtos_da_venda(
        quantidades,
        usuario,
        sessao,
        bloquear=True,
    )
    registros = []
    for item in venda.itens:
        produto = produtos[item.codigo_barras]
        quantidade_anterior = produto.quantidade
        produto.quantidade -= item.quantidade
        sessao.add(
            MovimentacaoEstoque(
                empresa_id=usuario.empresa_id,
                produto_id=produto.id,
                usuario_id=usuario.id,
                venda_id=venda.id,
                tipo="saida",
                quantidade=item.quantidade,
                quantidade_anterior=quantidade_anterior,
                quantidade_atual=produto.quantidade,
                nome_produto=produto.nome,
                codigo_barras=produto.codigo_barras,
                nome_usuario=usuario.nome,
                origem="venda",
            )
        )
        registros.append((item, produto))
    venda.status = "pago"
    venda.status_cobranca = "pago"
    venda.data_pagamento = datetime.now(timezone.utc).replace(tzinfo=None)
    return registros


def confirmar_pagamento_venda(
    venda: Venda,
    usuario: Usuario,
    sessao: Session,
    origem: str,
) -> list[tuple[ItemVenda, Produto]]:
    if venda.status == "pago":
        produtos = {
            produto.id: produto
            for produto in sessao.scalars(
                select(Produto).where(
                    Produto.id.in_(
                        [item.produto_id for item in venda.itens]
                    ),
                    Produto.empresa_id == venda.empresa_id,
                )
            ).all()
        }
        return [(item, produtos[item.produto_id]) for item in venda.itens]
    if venda.status != "aguardando_pagamento":
        raise HTTPException(409, "Esta venda nao pode ser confirmada.")

    registros = _baixar_estoque_venda(venda, usuario, sessao)
    registrar_auditoria(
        sessao,
        usuario,
        "pagamento_confirmado",
        "venda",
        venda.id,
        {
            "forma_pagamento": venda.forma_pagamento,
            "origem": origem,
            "cobranca_externa_id": venda.cobranca_externa_id,
        },
    )
    return registros


def registrar_venda(
    dados: VendaCriacao,
    usuario: Usuario,
    sessao: Session,
    confirmar_transacao: bool = True,
    precos_unitarios: dict[str, Decimal] | None = None,
    url_base_requisicao: str = "",
) -> tuple[Venda, list[tuple[ItemVenda, Produto]], str | None]:
    caixa = exigir_caixa_aberto(usuario, sessao)
    quantidades = defaultdict(int)
    for item in dados.itens:
        quantidades[item.codigo_barras.strip()] += item.quantidade
    produtos = _produtos_da_venda(quantidades, usuario, sessao)

    precos_aplicados = {
        codigo: Decimal(
            (precos_unitarios or {}).get(codigo, produtos[codigo].preco)
        )
        for codigo in quantidades
    }
    if any(preco < 0 for preco in precos_aplicados.values()):
        raise HTTPException(422, "O preco unitario nao pode ser negativo.")
    subtotal = sum(
        precos_aplicados[codigo] * quantidade
        for codigo, quantidade in quantidades.items()
    )
    desconto = Decimal(dados.desconto)
    if desconto > subtotal:
        raise HTTPException(422, "O desconto nao pode ser maior que o subtotal.")
    valor_total = (subtotal - desconto).quantize(Decimal("0.01"))
    valor_recebido = None
    troco_entregue = None
    if dados.forma_pagamento == "dinheiro":
        valor_recebido = Decimal(
            dados.valor_recebido
            if dados.valor_recebido is not None
            else valor_total
        ).quantize(Decimal("0.01"))
        if valor_recebido < valor_total:
            valor_faltante = valor_total - valor_recebido
            raise HTTPException(
                422,
                f"Valor recebido insuficiente. Faltam R$ {valor_faltante:.2f}.",
            )
        troco_entregue = valor_recebido - valor_total
    elif dados.valor_recebido is not None:
        raise HTTPException(
            422,
            "Valor recebido deve ser informado apenas para pagamento em dinheiro.",
        )
    cliente = None
    if dados.cliente_id:
        cliente = sessao.scalar(
            select(Cliente).where(
                Cliente.id == dados.cliente_id,
                Cliente.empresa_id == usuario.empresa_id,
                Cliente.ativo.is_(True),
            )
        )
        if not cliente:
            raise HTTPException(404, "Cliente nao encontrado.")

    eh_pix = dados.forma_pagamento == "pix"
    configuracao = None
    if eh_pix:
        configuracao = obter_configuracao_modelo(usuario.empresa_id, sessao)
        if not configuracao or not configuracao.ativo:
            raise HTTPException(
                422,
                "Configure uma conta PIX ativa antes de receber por PIX.",
            )

    venda = Venda(
        empresa_id=usuario.empresa_id,
        usuario_id=usuario.id,
        caixa_id=caixa.id,
        cliente_id=cliente.id if cliente else None,
        subtotal=subtotal,
        desconto=desconto,
        valor_total=valor_total,
        forma_pagamento=dados.forma_pagamento,
        valor_recebido=valor_recebido,
        troco_entregue=troco_entregue,
        status="aguardando_pagamento" if eh_pix else "pago",
        provedor_pagamento=configuracao.provedor if configuracao else None,
        status_cobranca="aguardando_pagamento" if eh_pix else "pago",
        data_pagamento=(
            None
            if eh_pix
            else datetime.now(timezone.utc).replace(tzinfo=None)
        ),
    )
    sessao.add(venda)
    sessao.flush()

    for codigo, quantidade in quantidades.items():
        produto = produtos[codigo]
        sessao.add(
            ItemVenda(
                empresa_id=usuario.empresa_id,
                venda_id=venda.id,
                produto_id=produto.id,
                codigo_barras=produto.codigo_barras,
                nome_produto=produto.nome,
                quantidade=quantidade,
                valor_unitario=precos_aplicados[codigo],
                valor_total=precos_aplicados[codigo] * quantidade,
                custo_unitario=produto.preco_compra,
                custo_total=Decimal(produto.preco_compra) * quantidade,
            )
        )
    sessao.flush()
    sessao.refresh(venda)
    sessao.refresh(venda, attribute_names=["itens"])

    qr_code = None
    if eh_pix:
        venda.referencia_pagamento = (
            f"NOVARIS-{usuario.empresa_id}-{venda.id}-{uuid4().hex[:12]}"
        )
        cobranca = criar_cobranca_pix(
            configuracao,
            venda,
            usuario,
            url_base_requisicao,
        )
        venda.cobranca_externa_id = cobranca.id_externo
        venda.codigo_pix = cobranca.codigo_pix
        venda.status_cobranca = (
            "pago"
            if cobranca.status == "approved"
            else "aguardando_pagamento"
        )
        qr_code = gerar_qr_code_base64(venda.codigo_pix)
        if cobranca.status == "approved":
            registros = confirmar_pagamento_venda(
                venda,
                usuario,
                sessao,
                "retorno_criacao_gateway",
            )
        else:
            registros = [
                (item, produtos[item.codigo_barras]) for item in venda.itens
            ]
    else:
        registros = _baixar_estoque_venda(venda, usuario, sessao)

    registrar_auditoria(
        sessao,
        usuario,
        "venda_registrada",
        "venda",
        venda.id,
        {
            "valor_total": venda.valor_total,
            "forma_pagamento": venda.forma_pagamento,
            "valor_recebido": venda.valor_recebido,
            "troco_entregue": venda.troco_entregue,
            "status": venda.status,
        },
    )
    if confirmar_transacao:
        sessao.commit()
    else:
        sessao.flush()
    sessao.refresh(venda)
    for item, produto in registros:
        sessao.refresh(item)
        sessao.refresh(produto)
    logger.info(
        "venda registrada empresa_id=%s usuario_id=%s venda_id=%s "
        "caixa_id=%s forma_pagamento=%s status=%s valor_total=%s",
        usuario.empresa_id,
        usuario.id,
        venda.id,
        venda.caixa_id,
        venda.forma_pagamento,
        venda.status,
        venda.valor_total,
    )
    return venda, registros, qr_code


def confirmar_pagamento_manual(
    venda_id: int,
    usuario: Usuario,
    sessao: Session,
) -> tuple[Venda, list[tuple[ItemVenda, Produto]]]:
    venda = sessao.scalar(
        select(Venda)
        .options(selectinload(Venda.itens))
        .where(
            Venda.id == venda_id,
            Venda.empresa_id == usuario.empresa_id,
            Venda.usuario_id == usuario.id,
        )
        .with_for_update()
    )
    if not venda:
        raise HTTPException(404, "Venda nao encontrada.")
    caixa = exigir_caixa_aberto(usuario, sessao)
    if venda.caixa_id != caixa.id:
        raise HTTPException(
            409,
            "A venda nao pertence ao caixa atualmente aberto.",
        )
    registros = confirmar_pagamento_venda(
        venda,
        usuario,
        sessao,
        "confirmacao_manual",
    )
    sessao.commit()
    sessao.refresh(venda)
    for item, produto in registros:
        sessao.refresh(produto)
    logger.info(
        "pagamento confirmado empresa_id=%s usuario_id=%s venda_id=%s",
        usuario.empresa_id,
        usuario.id,
        venda.id,
    )
    return venda, registros


def cancelar_venda(
    venda_id: int,
    dados: CancelamentoVendaCriacao,
    usuario: Usuario,
    sessao: Session,
) -> dict:
    venda = sessao.scalar(
        select(Venda)
        .options(
            selectinload(Venda.itens),
            selectinload(Venda.cancelamento),
        )
        .where(
            Venda.id == venda_id,
            Venda.empresa_id == usuario.empresa_id,
        )
        .with_for_update()
    )
    if not venda:
        raise HTTPException(404, "Venda nao encontrada.")
    if venda.status == "cancelado":
        raise HTTPException(409, "Esta venda ja foi cancelada.")
    if venda.status != "pago":
        raise HTTPException(
            409,
            "Somente vendas finalizadas e pagas podem ser canceladas.",
        )

    produtos = {
        produto.id: produto
        for produto in sessao.scalars(
            select(Produto)
            .where(
                Produto.empresa_id == usuario.empresa_id,
                Produto.id.in_([item.produto_id for item in venda.itens]),
            )
            .with_for_update()
        ).all()
    }
    if len(produtos) != len({item.produto_id for item in venda.itens}):
        raise HTTPException(
            409,
            "Nao foi possivel localizar todos os produtos da venda.",
        )

    total_devolvido = 0
    for item in venda.itens:
        produto = produtos[item.produto_id]
        quantidade_anterior = produto.quantidade
        produto.quantidade += item.quantidade
        total_devolvido += item.quantidade
        sessao.add(
            MovimentacaoEstoque(
                empresa_id=usuario.empresa_id,
                produto_id=produto.id,
                usuario_id=usuario.id,
                venda_id=venda.id,
                tipo="entrada",
                quantidade=item.quantidade,
                quantidade_anterior=quantidade_anterior,
                quantidade_atual=produto.quantidade,
                nome_produto=produto.nome,
                codigo_barras=produto.codigo_barras,
                nome_usuario=usuario.nome,
                origem="cancelamento_venda",
            )
        )

    motivo = dados.motivo.strip()
    cancelamento = CancelamentoVenda(
        empresa_id=usuario.empresa_id,
        venda_id=venda.id,
        usuario_id=usuario.id,
        motivo=motivo,
    )
    sessao.add(cancelamento)
    venda.status = "cancelado"
    registrar_auditoria(
        sessao,
        usuario,
        "venda_cancelada",
        "venda",
        venda.id,
        {
            "motivo": motivo,
            "valor_total": venda.valor_total,
            "produtos_devolvidos": total_devolvido,
        },
    )
    sessao.commit()
    sessao.refresh(cancelamento)
    logger.warning(
        "venda cancelada empresa_id=%s usuario_id=%s venda_id=%s",
        usuario.empresa_id,
        usuario.id,
        venda.id,
    )
    return {
        "venda_id": venda.id,
        "status": venda.status,
        "motivo": cancelamento.motivo,
        "data_cancelamento": cancelamento.data_cancelamento,
        "usuario_id": usuario.id,
        "nome_usuario": usuario.nome,
        "produtos_devolvidos": total_devolvido,
    }


def _serializar_venda_financeira(
    venda: Venda,
    autores: dict[int, Usuario],
) -> dict:
    cancelamento = venda.cancelamento
    autor_cancelamento = (
        autores.get(cancelamento.usuario_id)
        if cancelamento
        else None
    )
    return {
        "id": venda.id,
        "subtotal": venda.subtotal,
        "desconto": venda.desconto,
        "valor_total": venda.valor_total,
        "forma_pagamento": venda.forma_pagamento,
        "valor_recebido": venda.valor_recebido,
        "troco_entregue": venda.troco_entregue,
        "status": venda.status,
        "data_venda": venda.data_venda,
        "quantidade_itens": sum(item.quantidade for item in venda.itens),
        "usuario_id": venda.usuario_id,
        "nome_usuario": autores[venda.usuario_id].nome,
        "cargo_usuario": autores[venda.usuario_id].cargo,
        "caixa_id": venda.caixa_id,
        "cliente_id": venda.cliente_id,
        "nome_cliente": venda.cliente.nome if venda.cliente else None,
        "data_cancelamento": (
            cancelamento.data_cancelamento if cancelamento else None
        ),
        "motivo_cancelamento": (
            cancelamento.motivo if cancelamento else None
        ),
        "usuario_cancelamento_id": (
            cancelamento.usuario_id if cancelamento else None
        ),
        "nome_usuario_cancelamento": (
            autor_cancelamento.nome if autor_cancelamento else None
        ),
    }


def listar_vendas_financeiro(
    usuario: Usuario,
    sessao: Session,
    usuario_id: int | None = None,
) -> list[dict]:
    consulta = (
        select(Venda)
        .options(
            selectinload(Venda.itens),
            selectinload(Venda.cancelamento),
            selectinload(Venda.cliente),
        )
        .where(Venda.empresa_id == usuario.empresa_id)
        .order_by(Venda.data_venda.desc())
    )
    if usuario_id:
        consulta = consulta.where(Venda.usuario_id == usuario_id)
    vendas = sessao.scalars(consulta).all()
    autores = {
        autor.id: autor
        for autor in sessao.scalars(
            select(Usuario).where(Usuario.empresa_id == usuario.empresa_id)
        ).all()
    }
    return [_serializar_venda_financeira(venda, autores) for venda in vendas]


def listar_vendas_recentes_operador(
    usuario: Usuario,
    sessao: Session,
    limite: int = 8,
) -> list[dict]:
    consulta = (
        select(Venda)
        .options(
            selectinload(Venda.itens),
            selectinload(Venda.cancelamento),
            selectinload(Venda.cliente),
        )
        .where(Venda.empresa_id == usuario.empresa_id)
        .order_by(Venda.data_venda.desc())
        .limit(limite)
    )
    permissoes = permissoes_do_usuario(usuario)
    if (
        "vendas_relatorios" not in permissoes
        and "vendas_cancelar" not in permissoes
    ):
        consulta = consulta.where(Venda.usuario_id == usuario.id)
    vendas = sessao.scalars(consulta).all()
    autores = {
        autor.id: autor
        for autor in sessao.scalars(
            select(Usuario).where(Usuario.empresa_id == usuario.empresa_id)
        ).all()
    }
    return [_serializar_venda_financeira(venda, autores) for venda in vendas]


def resumir_vendas_por_operador(
    usuario: Usuario,
    sessao: Session,
) -> list[dict]:
    linhas = sessao.execute(
        select(
            Usuario.id,
            Usuario.nome,
            Usuario.cargo,
            func.coalesce(func.sum(Venda.valor_total), 0),
            func.count(Venda.id),
            func.coalesce(func.sum(Venda.desconto), 0),
            func.min(Venda.data_venda),
            func.max(Venda.data_venda),
        )
        .join(
            Venda,
            (Venda.usuario_id == Usuario.id)
            & (Venda.empresa_id == Usuario.empresa_id),
        )
        .where(
            Usuario.empresa_id == usuario.empresa_id,
            Venda.status == "pago",
        )
        .group_by(Usuario.id, Usuario.nome, Usuario.cargo)
        .order_by(func.sum(Venda.valor_total).desc())
    ).all()
    pagamentos = sessao.execute(
        select(
            Venda.usuario_id,
            Venda.forma_pagamento,
            func.sum(Venda.valor_total),
        )
        .where(
            Venda.empresa_id == usuario.empresa_id,
            Venda.status == "pago",
        )
        .group_by(Venda.usuario_id, Venda.forma_pagamento)
    ).all()
    formas_por_usuario: dict[int, dict] = defaultdict(dict)
    for usuario_id, forma, total in pagamentos:
        formas_por_usuario[usuario_id][forma] = total
    return [
        {
            "usuario_id": usuario_id,
            "nome_usuario": nome,
            "cargo_usuario": cargo,
            "total_vendido": total,
            "quantidade_vendas": quantidade,
            "total_descontos": descontos,
            "primeiro_horario": primeiro,
            "ultimo_horario": ultimo,
            "formas_pagamento": formas_por_usuario[usuario_id],
        }
        for (
            usuario_id,
            nome,
            cargo,
            total,
            quantidade,
            descontos,
            primeiro,
            ultimo,
        ) in linhas
    ]


def buscar_venda_empresa(
    venda_id: int,
    usuario: Usuario,
    sessao: Session,
) -> Venda:
    venda = sessao.scalar(
        select(Venda)
        .options(
            selectinload(Venda.itens),
            selectinload(Venda.cancelamento),
        )
        .where(
            Venda.id == venda_id,
            Venda.empresa_id == usuario.empresa_id,
        )
    )
    if not venda:
        raise HTTPException(404, "Venda nao encontrada.")
    return venda


def consultar_status_pagamento(
    venda_id: int,
    usuario: Usuario,
    sessao: Session,
) -> dict:
    venda = sessao.scalar(
        select(Venda).where(
            Venda.id == venda_id,
            Venda.empresa_id == usuario.empresa_id,
        )
    )
    if not venda:
        raise HTTPException(404, "Venda nao encontrada.")
    if (
        venda.usuario_id != usuario.id
        and "vendas_relatorios" not in permissoes_do_usuario(usuario)
    ):
        raise HTTPException(403, "Voce nao pode consultar esta venda.")
    return {
        "venda_id": venda.id,
        "status": venda.status,
        "status_cobranca": venda.status_cobranca,
        "data_pagamento": venda.data_pagamento,
    }
