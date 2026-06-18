from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.modelos.financeiro import LancamentoFinanceiro
from app.modelos.produto import MovimentacaoEstoque
from app.modelos.usuario import Usuario
from app.modelos.venda import Venda


def _moeda(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"))


def _limites_periodo(
    data_inicial: date | None,
    data_final: date | None,
) -> tuple[datetime | None, datetime | None]:
    inicio = (
        datetime.combine(data_inicial, time.min)
        if data_inicial
        else None
    )
    fim = (
        datetime.combine(data_final + timedelta(days=1), time.min)
        if data_final
        else None
    )
    return inicio, fim


def _aplicar_periodo(consulta, coluna, inicio, fim):
    if inicio:
        consulta = consulta.where(coluna >= inicio)
    if fim:
        consulta = consulta.where(coluna < fim)
    return consulta


def calcular_desempenho_usuarios(
    administrador: Usuario,
    sessao: Session,
    data_inicial: date | None = None,
    data_final: date | None = None,
    usuario_id: int | None = None,
) -> list[dict]:
    inicio, fim = _limites_periodo(data_inicial, data_final)
    consulta_usuarios = select(Usuario).where(
        Usuario.empresa_id == administrador.empresa_id
    )
    if usuario_id:
        consulta_usuarios = consulta_usuarios.where(Usuario.id == usuario_id)
    usuarios = sessao.scalars(
        consulta_usuarios.order_by(Usuario.nome)
    ).all()
    ids = [usuario.id for usuario in usuarios]
    if not ids:
        return []

    consulta_vendas = select(
        Venda.usuario_id,
        func.count(Venda.id),
        func.coalesce(func.sum(Venda.valor_total), 0),
        func.coalesce(func.sum(Venda.desconto), 0),
        func.min(Venda.data_venda),
        func.max(Venda.data_venda),
    ).where(
        Venda.empresa_id == administrador.empresa_id,
        Venda.usuario_id.in_(ids),
        Venda.status == "pago",
    )
    consulta_vendas = _aplicar_periodo(
        consulta_vendas,
        Venda.data_venda,
        inicio,
        fim,
    )
    vendas = {
        linha[0]: linha[1:]
        for linha in sessao.execute(
            consulta_vendas.group_by(Venda.usuario_id)
        ).all()
    }

    consulta_pagamentos = select(
        Venda.usuario_id,
        Venda.forma_pagamento,
        func.sum(Venda.valor_total),
    ).where(
        Venda.empresa_id == administrador.empresa_id,
        Venda.usuario_id.in_(ids),
        Venda.status == "pago",
    )
    consulta_pagamentos = _aplicar_periodo(
        consulta_pagamentos,
        Venda.data_venda,
        inicio,
        fim,
    )
    pagamentos: dict[int, dict[str, Decimal]] = defaultdict(dict)
    for autor_id, forma, total in sessao.execute(
        consulta_pagamentos.group_by(
            Venda.usuario_id,
            Venda.forma_pagamento,
        )
    ).all():
        pagamentos[autor_id][forma] = _moeda(total)

    consulta_estoque = select(
        MovimentacaoEstoque.usuario_id,
        func.count(MovimentacaoEstoque.id),
        func.sum(
            case(
                (MovimentacaoEstoque.tipo == "entrada", 1),
                else_=0,
            )
        ),
        func.sum(
            case(
                (MovimentacaoEstoque.tipo == "saida", 1),
                else_=0,
            )
        ),
        func.sum(
            case(
                (
                    MovimentacaoEstoque.tipo == "entrada",
                    MovimentacaoEstoque.quantidade,
                ),
                else_=0,
            )
        ),
        func.sum(
            case(
                (
                    MovimentacaoEstoque.tipo == "saida",
                    MovimentacaoEstoque.quantidade,
                ),
                else_=0,
            )
        ),
    ).where(
        MovimentacaoEstoque.empresa_id == administrador.empresa_id,
        MovimentacaoEstoque.usuario_id.in_(ids),
    )
    consulta_estoque = _aplicar_periodo(
        consulta_estoque,
        MovimentacaoEstoque.data_movimentacao,
        inicio,
        fim,
    )
    estoque = {
        linha[0]: linha[1:]
        for linha in sessao.execute(
            consulta_estoque.group_by(MovimentacaoEstoque.usuario_id)
        ).all()
    }

    consulta_financeiro = select(
        LancamentoFinanceiro.usuario_id,
        func.count(LancamentoFinanceiro.id),
        func.sum(
            case(
                (
                    LancamentoFinanceiro.tipo == "entrada",
                    LancamentoFinanceiro.valor,
                ),
                else_=0,
            )
        ),
        func.sum(
            case(
                (
                    LancamentoFinanceiro.tipo == "saida",
                    LancamentoFinanceiro.valor,
                ),
                else_=0,
            )
        ),
    ).where(
        LancamentoFinanceiro.empresa_id == administrador.empresa_id,
        LancamentoFinanceiro.usuario_id.in_(ids),
    )
    consulta_financeiro = _aplicar_periodo(
        consulta_financeiro,
        LancamentoFinanceiro.data_lancamento,
        inicio,
        fim,
    )
    financeiro = {
        linha[0]: linha[1:]
        for linha in sessao.execute(
            consulta_financeiro.group_by(LancamentoFinanceiro.usuario_id)
        ).all()
    }

    resultado = []
    for usuario in usuarios:
        dados_vendas = vendas.get(
            usuario.id,
            (0, Decimal("0"), Decimal("0"), None, None),
        )
        dados_estoque = estoque.get(usuario.id, (0, 0, 0, 0, 0))
        dados_financeiros = financeiro.get(
            usuario.id,
            (0, Decimal("0"), Decimal("0")),
        )
        resultado.append({
            "usuario_id": usuario.id,
            "nome_usuario": usuario.nome,
            "cargo_usuario": usuario.cargo,
            "ativo": usuario.ativo,
            "quantidade_vendas": dados_vendas[0],
            "total_vendido": _moeda(dados_vendas[1]),
            "total_descontos": _moeda(dados_vendas[2]),
            "primeira_venda": dados_vendas[3],
            "ultima_venda": dados_vendas[4],
            "formas_pagamento": pagamentos[usuario.id],
            "movimentacoes_estoque": dados_estoque[0],
            "entradas_estoque": dados_estoque[1] or 0,
            "saidas_estoque": dados_estoque[2] or 0,
            "unidades_entrada": dados_estoque[3] or 0,
            "unidades_saida": dados_estoque[4] or 0,
            "lancamentos_financeiros": dados_financeiros[0],
            "entradas_financeiras": _moeda(dados_financeiros[1]),
            "saidas_financeiras": _moeda(dados_financeiros[2]),
        })
    return sorted(
        resultado,
        key=lambda item: (
            item["total_vendido"],
            item["movimentacoes_estoque"],
            item["lancamentos_financeiros"],
        ),
        reverse=True,
    )
