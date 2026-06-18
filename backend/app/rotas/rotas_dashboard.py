from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.autenticacao.seguranca import obter_usuario_logado
from app.banco.conexao import obter_sessao_banco
from app.esquemas.dashboard import DashboardResposta
from app.modelos.produto import Produto
from app.modelos.cliente import Cliente
from app.modelos.comercial import Orcamento, PedidoCompra
from app.modelos.operacoes import DevolucaoVenda, ItemDevolucaoVenda
from app.modelos.usuario import Usuario
from app.modelos.venda import ItemVenda, Venda
from app.servicos.servico_permissoes import (
    garantir_permissao,
    pode_visualizar_alertas_estoque,
    permissoes_do_usuario,
)
from app.servicos.servico_backup import garantir_backup_automatico


roteador_dashboard = APIRouter(tags=["Dashboard"])


def inicio_do_dia(valor: date) -> datetime:
    return datetime.combine(valor, time.min)


def somar_vendas(
    sessao: Session,
    empresa_id: int,
    inicio: datetime,
    fim: datetime,
) -> Decimal:
    vendas = Decimal(
        sessao.scalar(
            select(func.coalesce(func.sum(Venda.valor_total), 0)).where(
                Venda.empresa_id == empresa_id,
                Venda.status == "pago",
                Venda.data_venda >= inicio,
                Venda.data_venda < fim,
            )
        )
    )
    adicionais, estornos = sessao.execute(
        select(
            func.coalesce(func.sum(DevolucaoVenda.valor_adicional), 0),
            func.coalesce(func.sum(DevolucaoVenda.valor_estornado), 0),
        ).where(
            DevolucaoVenda.empresa_id == empresa_id,
            DevolucaoVenda.data_operacao >= inicio,
            DevolucaoVenda.data_operacao < fim,
        )
    ).one()
    return vendas + Decimal(adicionais) - Decimal(estornos)


@roteador_dashboard.get(
    "/dashboard",
    response_model=DashboardResposta,
    summary="Carregar dashboard inteligente",
)
def carregar_dashboard(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "dashboard_visualizar")
    if "backup_gerenciar" in permissoes_do_usuario(usuario):
        garantir_backup_automatico(usuario, sessao)
    hoje = datetime.now(timezone.utc).date()
    amanha = hoje + timedelta(days=1)
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    inicio_mes = hoje.replace(day=1)
    inicio_grafico = hoje - timedelta(days=6)
    inicio_hoje_dt = inicio_do_dia(hoje)
    inicio_mes_dt = inicio_do_dia(inicio_mes)
    fim_amanha_dt = inicio_do_dia(amanha)

    total_produtos = sessao.scalar(
        select(func.count(Produto.id)).where(
            Produto.empresa_id == usuario.empresa_id,
            Produto.ativo.is_(True),
        )
    ) or 0
    total_clientes = sessao.scalar(
        select(func.count(Cliente.id)).where(
            Cliente.empresa_id == usuario.empresa_id,
            Cliente.ativo.is_(True),
        )
    ) or 0
    faturamento_diario = somar_vendas(
        sessao,
        usuario.empresa_id,
        inicio_hoje_dt,
        fim_amanha_dt,
    )
    faturamento_semanal = somar_vendas(
        sessao,
        usuario.empresa_id,
        inicio_do_dia(inicio_semana),
        fim_amanha_dt,
    )
    faturamento_mensal = somar_vendas(
        sessao,
        usuario.empresa_id,
        inicio_mes_dt,
        fim_amanha_dt,
    )
    total_vendas = Decimal(
        sessao.scalar(
            select(func.coalesce(func.sum(Venda.valor_total), 0)).where(
                Venda.empresa_id == usuario.empresa_id,
                Venda.status == "pago",
            )
        )
    )
    ajustes_totais = sessao.execute(
        select(
            func.coalesce(func.sum(DevolucaoVenda.valor_adicional), 0),
            func.coalesce(func.sum(DevolucaoVenda.valor_estornado), 0),
        ).where(DevolucaoVenda.empresa_id == usuario.empresa_id)
    ).one()
    total_vendas += Decimal(ajustes_totais[0]) - Decimal(ajustes_totais[1])
    quantidade_vendas = sessao.scalar(
        select(func.count(Venda.id)).where(
            Venda.empresa_id == usuario.empresa_id,
            Venda.status == "pago",
            Venda.data_venda >= inicio_mes_dt,
            Venda.data_venda < fim_amanha_dt,
        )
    ) or 0
    custo_mensal = Decimal(
        sessao.scalar(
            select(func.coalesce(func.sum(ItemVenda.custo_total), 0))
            .join(Venda, Venda.id == ItemVenda.venda_id)
            .where(
                Venda.empresa_id == usuario.empresa_id,
                Venda.status == "pago",
                Venda.data_venda >= inicio_mes_dt,
                Venda.data_venda < fim_amanha_dt,
            )
        )
    )
    custos_operacoes = sessao.execute(
        select(
            func.coalesce(
                func.sum(
                    ItemDevolucaoVenda.custo_unitario
                    * ItemDevolucaoVenda.quantidade
                ).filter(ItemDevolucaoVenda.direcao == "devolvido"),
                0,
            ),
            func.coalesce(
                func.sum(
                    ItemDevolucaoVenda.custo_unitario
                    * ItemDevolucaoVenda.quantidade
                ).filter(ItemDevolucaoVenda.direcao == "novo"),
                0,
            ),
        )
        .join(
            DevolucaoVenda,
            DevolucaoVenda.id == ItemDevolucaoVenda.devolucao_id,
        )
        .where(
            DevolucaoVenda.empresa_id == usuario.empresa_id,
            DevolucaoVenda.data_operacao >= inicio_mes_dt,
            DevolucaoVenda.data_operacao < fim_amanha_dt,
        )
    ).one()
    custo_mensal = (
        custo_mensal
        - Decimal(custos_operacoes[0])
        + Decimal(custos_operacoes[1])
    )
    lucro_mensal = faturamento_mensal - custo_mensal
    produtos_estoque_baixo = 0
    unidades_para_repor = 0
    produtos_proximos_reposicao = 0
    if pode_visualizar_alertas_estoque(usuario):
        produtos_estoque_baixo = sessao.scalar(
            select(func.count(Produto.id)).where(
                Produto.empresa_id == usuario.empresa_id,
                Produto.ativo.is_(True),
                Produto.quantidade <= Produto.estoque_minimo,
            )
        ) or 0
        unidades_para_repor = sessao.scalar(
            select(
                func.coalesce(
                    func.sum(Produto.estoque_minimo - Produto.quantidade),
                    0,
                )
            ).where(
                Produto.empresa_id == usuario.empresa_id,
                Produto.ativo.is_(True),
                Produto.quantidade < Produto.estoque_minimo,
            )
        ) or 0
        produtos_empresa = sessao.scalars(
            select(Produto).where(
                Produto.empresa_id == usuario.empresa_id,
                Produto.ativo.is_(True),
            )
        ).all()
        produtos_proximos_reposicao = sum(
            1
            for produto in produtos_empresa
            if produto.quantidade <= max(
                produto.estoque_minimo + 1,
                int(produto.estoque_minimo * 1.25),
            )
        )
    pedidos_compra_pendentes = sessao.scalar(
        select(func.count(PedidoCompra.id)).where(
            PedidoCompra.empresa_id == usuario.empresa_id,
            PedidoCompra.status.in_(["pendente", "enviado"]),
        )
    ) or 0
    orcamentos_pendentes = sessao.scalar(
        select(func.count(Orcamento.id)).where(
            Orcamento.empresa_id == usuario.empresa_id,
            Orcamento.status == "pendente",
        )
    ) or 0
    total_orcamentos = sessao.scalar(
        select(func.count(Orcamento.id)).where(
            Orcamento.empresa_id == usuario.empresa_id,
        )
    ) or 0
    convertidos = sessao.scalar(
        select(func.count(Orcamento.id)).where(
            Orcamento.empresa_id == usuario.empresa_id,
            Orcamento.status == "convertido",
        )
    ) or 0
    clientes_destaque = sessao.execute(
        select(
            Cliente.id,
            Cliente.nome,
            func.sum(Venda.valor_total),
            func.count(Venda.id),
        )
        .join(
            Venda,
            (Venda.cliente_id == Cliente.id)
            & (Venda.empresa_id == Cliente.empresa_id),
        )
        .where(
            Cliente.empresa_id == usuario.empresa_id,
            Venda.status == "pago",
        )
        .group_by(Cliente.id, Cliente.nome)
        .order_by(func.sum(Venda.valor_total).desc())
        .limit(5)
    ).all()
    mais_vendidos = sessao.execute(
        select(
            ItemVenda.nome_produto,
            ItemVenda.codigo_barras,
            func.sum(ItemVenda.quantidade).label("quantidade"),
            func.sum(ItemVenda.valor_total).label("faturamento"),
        )
        .join(Venda, Venda.id == ItemVenda.venda_id)
        .where(
            Venda.empresa_id == usuario.empresa_id,
            Venda.status == "pago",
            Venda.data_venda >= inicio_mes_dt,
            Venda.data_venda < fim_amanha_dt,
        )
        .group_by(ItemVenda.nome_produto, ItemVenda.codigo_barras)
        .order_by(func.sum(ItemVenda.quantidade).desc())
        .limit(5)
    ).all()
    vendas_grafico = sessao.execute(
        select(Venda.data_venda, Venda.valor_total).where(
            Venda.empresa_id == usuario.empresa_id,
            Venda.status == "pago",
            Venda.data_venda >= inicio_do_dia(inicio_grafico),
            Venda.data_venda < fim_amanha_dt,
        )
    ).all()
    ajustes_grafico = sessao.execute(
        select(
            DevolucaoVenda.data_operacao,
            DevolucaoVenda.valor_adicional,
            DevolucaoVenda.valor_estornado,
        ).where(
            DevolucaoVenda.empresa_id == usuario.empresa_id,
            DevolucaoVenda.data_operacao >= inicio_do_dia(inicio_grafico),
            DevolucaoVenda.data_operacao < fim_amanha_dt,
        )
    ).all()
    valores_por_dia = {
        inicio_grafico + timedelta(days=indice): Decimal("0")
        for indice in range(7)
    }
    for data_venda, valor in vendas_grafico:
        valores_por_dia[data_venda.date()] += Decimal(valor)
    for data_operacao, adicional, estornado in ajustes_grafico:
        valores_por_dia[data_operacao.date()] += (
            Decimal(adicional) - Decimal(estornado)
        )

    return DashboardResposta(
        nome_empresa=usuario.empresa.nome,
        nome_usuario=usuario.nome,
        total_clientes=total_clientes,
        total_produtos=total_produtos,
        total_vendas=float(total_vendas),
        lucro_mensal=float(lucro_mensal),
        produtos_estoque_baixo=produtos_estoque_baixo,
        unidades_para_repor=unidades_para_repor,
        faturamento_diario=float(faturamento_diario),
        faturamento_semanal=float(faturamento_semanal),
        faturamento_mensal=float(faturamento_mensal),
        quantidade_vendas=quantidade_vendas,
        ticket_medio=(
            float(faturamento_mensal / quantidade_vendas)
            if quantidade_vendas
            else 0
        ),
        margem_bruta=(
            round(float(lucro_mensal / faturamento_mensal * 100), 2)
            if faturamento_mensal
            else 0
        ),
        produtos_proximos_reposicao=produtos_proximos_reposicao,
        pedidos_compra_pendentes=pedidos_compra_pendentes,
        orcamentos_pendentes=orcamentos_pendentes,
        taxa_conversao_orcamentos=(
            round(convertidos / total_orcamentos * 100, 2)
            if total_orcamentos else 0
        ),
        clientes_mais_compram=[
            {
                "cliente_id": cliente_id,
                "nome": nome,
                "total_gasto": float(total),
                "quantidade_compras": quantidade,
            }
            for cliente_id, nome, total, quantidade in clientes_destaque
        ],
        produtos_mais_vendidos=[
            {
                "nome": nome,
                "codigo_barras": codigo,
                "quantidade": quantidade,
                "faturamento": float(faturamento),
            }
            for nome, codigo, quantidade, faturamento in mais_vendidos
        ],
        faturamento_ultimos_dias=[
            {
                "data": dia.strftime("%d/%m"),
                "valor": float(valor),
            }
            for dia, valor in valores_por_dia.items()
        ],
    )
