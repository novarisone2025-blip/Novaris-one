from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.esquemas.caixa import (
    AberturaCaixa,
    FechamentoCaixa,
    MovimentacaoCaixaCriacao,
)
from app.modelos.caixa import Caixa
from app.modelos.operacoes import DevolucaoVenda, MovimentacaoCaixa
from app.modelos.usuario import Usuario
from app.modelos.venda import Venda
from app.servicos.servico_auditoria import registrar_auditoria


def obter_caixa_aberto(
    usuario: Usuario,
    sessao: Session,
    bloquear: bool = False,
) -> Caixa | None:
    consulta = select(Caixa).where(
        Caixa.empresa_id == usuario.empresa_id,
        Caixa.usuario_id == usuario.id,
        Caixa.status == "aberto",
    )
    if bloquear:
        consulta = consulta.with_for_update()
    return sessao.scalar(consulta)


def exigir_caixa_aberto(usuario: Usuario, sessao: Session) -> Caixa:
    caixa = obter_caixa_aberto(usuario, sessao)
    if not caixa:
        raise HTTPException(
            409,
            "Abra o caixa antes de registrar uma venda.",
        )
    return caixa


def _resumo_vendas(caixa: Caixa, sessao: Session) -> dict:
    totais = sessao.execute(
        select(
            func.count(
                case((Venda.status == "pago", Venda.id))
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            (Venda.status == "pago")
                            & (Venda.forma_pagamento == "dinheiro"),
                            Venda.valor_total,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            (Venda.status == "pago")
                            & (Venda.forma_pagamento == "pix"),
                            Venda.valor_total,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            (Venda.status == "pago")
                            & (Venda.forma_pagamento == "debito"),
                            Venda.valor_total,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            (Venda.status == "pago")
                            & (Venda.forma_pagamento == "credito"),
                            Venda.valor_total,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (Venda.status == "pago", Venda.desconto),
                        else_=0,
                    )
                ),
                0,
            ),
            func.count(
                case((Venda.status == "cancelado", Venda.id))
            ),
            func.coalesce(
                func.sum(
                    case(
                        (Venda.status == "cancelado", Venda.valor_total),
                        else_=0,
                    )
                ),
                0,
            ),
            func.count(
                case(
                    (Venda.status == "aguardando_pagamento", Venda.id)
                )
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            (Venda.status == "pago")
                            & (Venda.forma_pagamento == "dinheiro"),
                            Venda.valor_recebido,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            (Venda.status == "pago")
                            & (Venda.forma_pagamento == "dinheiro"),
                            Venda.troco_entregue,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
        ).where(
            Venda.empresa_id == caixa.empresa_id,
            Venda.caixa_id == caixa.id,
        )
    ).one()
    totais_operacoes = sessao.execute(
        select(
            func.coalesce(func.sum(DevolucaoVenda.valor_estornado), 0),
            func.coalesce(func.sum(DevolucaoVenda.valor_adicional), 0),
            func.coalesce(
                func.sum(
                    case(
                        (
                            DevolucaoVenda.forma_pagamento == "dinheiro",
                            DevolucaoVenda.valor_estornado,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            DevolucaoVenda.forma_pagamento == "dinheiro",
                            DevolucaoVenda.valor_adicional,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
        ).where(
            DevolucaoVenda.empresa_id == caixa.empresa_id,
            DevolucaoVenda.caixa_id == caixa.id,
        )
    ).one()
    totais_caixa = sessao.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (MovimentacaoCaixa.tipo == "sangria", MovimentacaoCaixa.valor),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (MovimentacaoCaixa.tipo == "reforco", MovimentacaoCaixa.valor),
                        else_=0,
                    )
                ),
                0,
            ),
        ).where(
            MovimentacaoCaixa.empresa_id == caixa.empresa_id,
            MovimentacaoCaixa.caixa_id == caixa.id,
        )
    ).one()
    return {
        "quantidade_vendas": totais[0],
        "total_dinheiro": Decimal(totais[1]),
        "total_pix": Decimal(totais[2]),
        "total_debito": Decimal(totais[3]),
        "total_credito": Decimal(totais[4]),
        "total_descontos": Decimal(totais[5]),
        "quantidade_cancelamentos": totais[6],
        "total_cancelamentos": Decimal(totais[7]),
        "vendas_pendentes": totais[8],
        "total_recebido_dinheiro": Decimal(totais[9]),
        "total_troco_entregue": Decimal(totais[10]),
        "total_devolucoes": Decimal(totais_operacoes[0]),
        "total_adicionais_troca": Decimal(totais_operacoes[1]),
        "total_devolucoes_dinheiro": Decimal(totais_operacoes[2]),
        "total_adicionais_troca_dinheiro": Decimal(totais_operacoes[3]),
        "total_sangrias": Decimal(totais_caixa[0]),
        "total_reforcos": Decimal(totais_caixa[1]),
    }


def montar_resposta_caixa(
    caixa: Caixa,
    usuario: Usuario,
    sessao: Session,
) -> dict:
    resumo = _resumo_vendas(caixa, sessao)
    esperado = (
        Decimal(caixa.valor_esperado)
        if caixa.valor_esperado is not None
        else (
            Decimal(caixa.valor_inicial)
            + resumo["total_dinheiro"]
            + resumo["total_adicionais_troca_dinheiro"]
            + resumo["total_reforcos"]
            - resumo["total_devolucoes_dinheiro"]
            - resumo["total_sangrias"]
        )
    )
    diferenca = (
        Decimal(caixa.diferenca)
        if caixa.diferenca is not None
        else None
    )
    situacao = "nao_informada"
    if diferenca is not None:
        situacao = (
            "sobra"
            if diferenca > 0
            else "falta"
            if diferenca < 0
            else "correto"
        )
    movimentos = sessao.scalars(
        select(MovimentacaoCaixa)
        .where(
            MovimentacaoCaixa.empresa_id == caixa.empresa_id,
            MovimentacaoCaixa.caixa_id == caixa.id,
        )
        .order_by(MovimentacaoCaixa.data_movimento.desc())
    ).all()
    return {
        "id": caixa.id,
        "usuario_id": caixa.usuario_id,
        "nome_usuario": usuario.nome,
        "cargo_usuario": usuario.cargo,
        "status": caixa.status,
        "valor_inicial": caixa.valor_inicial,
        **resumo,
        "total_vendido": (
            resumo["total_dinheiro"]
            + resumo["total_pix"]
            + resumo["total_debito"]
            + resumo["total_credito"]
        ),
        "valor_esperado": esperado,
        "valor_real": caixa.valor_real,
        "diferenca": diferenca,
        "situacao_diferenca": situacao,
        "data_abertura": caixa.data_abertura,
        "data_fechamento": caixa.data_fechamento,
        "movimentacoes_caixa": [
            {
                "id": movimento.id,
                "caixa_id": movimento.caixa_id,
                "usuario_id": movimento.usuario_id,
                "nome_usuario": usuario.nome,
                "tipo": movimento.tipo,
                "motivo": movimento.motivo,
                "valor": movimento.valor,
                "data_movimento": movimento.data_movimento,
            }
            for movimento in movimentos
        ],
    }


def listar_caixas_ativos(
    usuario: Usuario,
    sessao: Session,
) -> list[dict]:
    linhas = sessao.execute(
        select(Caixa, Usuario)
        .join(
            Usuario,
            (Usuario.id == Caixa.usuario_id)
            & (Usuario.empresa_id == Caixa.empresa_id),
        )
        .where(
            Caixa.empresa_id == usuario.empresa_id,
            Caixa.status == "aberto",
        )
        .order_by(Caixa.data_abertura)
    ).all()
    return [
        montar_resposta_caixa(caixa, responsavel, sessao)
        for caixa, responsavel in linhas
    ]


def abrir_caixa(
    dados: AberturaCaixa,
    usuario: Usuario,
    sessao: Session,
) -> dict:
    if obter_caixa_aberto(usuario, sessao, bloquear=True):
        raise HTTPException(409, "Este usuario ja possui um caixa aberto.")
    caixa = Caixa(
        empresa_id=usuario.empresa_id,
        usuario_id=usuario.id,
        valor_inicial=dados.valor_inicial,
        status="aberto",
    )
    sessao.add(caixa)
    sessao.flush()
    registrar_auditoria(
        sessao,
        usuario,
        "caixa_aberto",
        "caixa",
        caixa.id,
        {"valor_inicial": caixa.valor_inicial},
    )
    sessao.commit()
    sessao.refresh(caixa)
    return montar_resposta_caixa(caixa, usuario, sessao)


def fechar_caixa(
    dados: FechamentoCaixa,
    usuario: Usuario,
    sessao: Session,
) -> dict:
    caixa = obter_caixa_aberto(usuario, sessao, bloquear=True)
    if not caixa:
        raise HTTPException(404, "Nenhum caixa aberto para este usuario.")
    resumo = _resumo_vendas(caixa, sessao)
    if resumo["vendas_pendentes"]:
        raise HTTPException(
            409,
            "Confirme ou cancele os pagamentos pendentes antes de fechar.",
        )
    esperado = (
        Decimal(caixa.valor_inicial)
        + resumo["total_dinheiro"]
        + resumo["total_adicionais_troca_dinheiro"]
        + resumo["total_reforcos"]
        - resumo["total_devolucoes_dinheiro"]
        - resumo["total_sangrias"]
    )
    caixa.status = "fechado"
    caixa.total_dinheiro = resumo["total_dinheiro"]
    caixa.total_pix = resumo["total_pix"]
    caixa.total_debito = resumo["total_debito"]
    caixa.total_credito = resumo["total_credito"]
    caixa.total_descontos = resumo["total_descontos"]
    caixa.total_cancelamentos = resumo["total_cancelamentos"]
    caixa.total_sangrias = resumo["total_sangrias"]
    caixa.total_reforcos = resumo["total_reforcos"]
    caixa.total_devolucoes_dinheiro = resumo["total_devolucoes_dinheiro"]
    caixa.valor_esperado = esperado
    caixa.valor_real = dados.valor_real
    caixa.diferenca = Decimal(dados.valor_real) - esperado
    caixa.data_fechamento = datetime.now(timezone.utc).replace(tzinfo=None)
    registrar_auditoria(
        sessao,
        usuario,
        "caixa_fechado",
        "caixa",
        caixa.id,
        {
            "valor_esperado": caixa.valor_esperado,
            "valor_real": caixa.valor_real,
            "diferenca": caixa.diferenca,
        },
    )
    sessao.commit()
    sessao.refresh(caixa)
    return montar_resposta_caixa(caixa, usuario, sessao)


def registrar_movimentacao_caixa(
    tipo: str,
    dados: MovimentacaoCaixaCriacao,
    usuario: Usuario,
    sessao: Session,
) -> dict:
    caixa = obter_caixa_aberto(usuario, sessao, bloquear=True)
    if not caixa:
        raise HTTPException(409, "Abra o caixa antes de realizar esta operacao.")
    resumo = _resumo_vendas(caixa, sessao)
    disponivel = (
        Decimal(caixa.valor_inicial)
        + resumo["total_dinheiro"]
        + resumo["total_adicionais_troca_dinheiro"]
        + resumo["total_reforcos"]
        - resumo["total_devolucoes_dinheiro"]
        - resumo["total_sangrias"]
    )
    if tipo == "sangria" and Decimal(dados.valor) > disponivel:
        raise HTTPException(
            422,
            f"Valor de sangria maior que o dinheiro esperado no caixa: {disponivel:.2f}.",
        )
    movimento = MovimentacaoCaixa(
        empresa_id=usuario.empresa_id,
        caixa_id=caixa.id,
        usuario_id=usuario.id,
        tipo=tipo,
        motivo=dados.motivo.strip(),
        valor=dados.valor,
    )
    sessao.add(movimento)
    sessao.flush()
    registrar_auditoria(
        sessao,
        usuario,
        f"caixa_{tipo}",
        "caixa",
        caixa.id,
        {
            "movimento_id": movimento.id,
            "valor": movimento.valor,
            "motivo": movimento.motivo,
        },
    )
    sessao.commit()
    sessao.refresh(movimento)
    return {
        "id": movimento.id,
        "caixa_id": caixa.id,
        "usuario_id": usuario.id,
        "nome_usuario": usuario.nome,
        "tipo": movimento.tipo,
        "motivo": movimento.motivo,
        "valor": movimento.valor,
        "data_movimento": movimento.data_movimento,
    }


def buscar_caixa_empresa(
    caixa_id: int,
    usuario: Usuario,
    sessao: Session,
) -> tuple[Caixa, Usuario]:
    linha = sessao.execute(
        select(Caixa, Usuario)
        .join(
            Usuario,
            (Usuario.id == Caixa.usuario_id)
            & (Usuario.empresa_id == Caixa.empresa_id),
        )
        .where(
            Caixa.id == caixa_id,
            Caixa.empresa_id == usuario.empresa_id,
        )
    ).first()
    if not linha:
        raise HTTPException(404, "Caixa nao encontrado.")
    return linha
