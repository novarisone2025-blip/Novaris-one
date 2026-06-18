from datetime import date

from fastapi import APIRouter, Depends, Path
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.autenticacao.seguranca import obter_usuario_logado
from app.banco.conexao import obter_sessao_banco
from app.esquemas.operacoes import RelatorioAvancadoResposta
from app.modelos.usuario import Usuario
from app.modelos.produto import Produto
from app.modelos.caixa import Caixa
from app.servicos.servico_auditoria import registrar_auditoria
from app.servicos.servico_permissoes import garantir_permissao
from app.servicos.servico_relatorios_avancados import (
    gerar_relatorio_avancado,
    relatorio_avancado_excel,
    relatorio_avancado_pdf,
)


roteador_relatorios = APIRouter(
    prefix="/relatorios",
    tags=["Relatorios avancados"],
)


@roteador_relatorios.get("/opcoes")
def consultar_opcoes_relatorio(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "relatorios_financeiros")
    produtos = sessao.scalars(
        select(Produto)
        .where(
            Produto.empresa_id == usuario.empresa_id,
            Produto.ativo.is_(True),
        )
        .order_by(Produto.nome)
    ).all()
    usuarios = sessao.scalars(
        select(Usuario)
        .where(Usuario.empresa_id == usuario.empresa_id)
        .order_by(Usuario.nome)
    ).all()
    caixas = sessao.scalars(
        select(Caixa)
        .where(Caixa.empresa_id == usuario.empresa_id)
        .order_by(Caixa.data_abertura.desc())
        .limit(200)
    ).all()
    return {
        "produtos": [
            {
                "id": item.id,
                "nome": item.nome,
                "categoria": item.categoria,
            }
            for item in produtos
        ],
        "usuarios": [
            {"id": item.id, "nome": item.nome, "cargo": item.cargo}
            for item in usuarios
        ],
        "caixas": [
            {
                "id": item.id,
                "usuario_id": item.usuario_id,
                "data_abertura": item.data_abertura,
            }
            for item in caixas
        ],
    }


def _dados_relatorio(
    usuario,
    sessao,
    periodo,
    data_inicial,
    data_final,
    produto_id,
    categoria,
    usuario_id,
    caixa_id,
    forma_pagamento,
):
    return gerar_relatorio_avancado(
        usuario,
        sessao,
        periodo,
        data_inicial,
        data_final,
        produto_id,
        categoria,
        usuario_id,
        caixa_id,
        forma_pagamento,
    )


@roteador_relatorios.get("/vendas", response_model=RelatorioAvancadoResposta)
def consultar_relatorio_vendas(
    periodo: str = "mes",
    data_inicial: date | None = None,
    data_final: date | None = None,
    produto_id: int | None = None,
    categoria: str | None = None,
    usuario_id: int | None = None,
    caixa_id: int | None = None,
    forma_pagamento: str | None = None,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "relatorios_financeiros")
    return _dados_relatorio(
        usuario, sessao, periodo, data_inicial, data_final, produto_id,
        categoria, usuario_id, caixa_id, forma_pagamento,
    )


@roteador_relatorios.get("/vendas/{formato}")
def exportar_relatorio_vendas(
    formato: str = Path(pattern="^(pdf|excel)$"),
    periodo: str = "mes",
    data_inicial: date | None = None,
    data_final: date | None = None,
    produto_id: int | None = None,
    categoria: str | None = None,
    usuario_id: int | None = None,
    caixa_id: int | None = None,
    forma_pagamento: str | None = None,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "relatorios_financeiros")
    dados = _dados_relatorio(
        usuario, sessao, periodo, data_inicial, data_final, produto_id,
        categoria, usuario_id, caixa_id, forma_pagamento,
    )
    registrar_auditoria(
        sessao,
        usuario,
        "relatorio_avancado_gerado",
        "vendas",
        detalhes={"formato": formato, "periodo": periodo},
    )
    sessao.commit()
    if formato == "pdf":
        return StreamingResponse(
            relatorio_avancado_pdf(dados, usuario.empresa.nome),
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    'attachment; filename="relatorio-avancado-vendas.pdf"'
                )
            },
        )
    return StreamingResponse(
        relatorio_avancado_excel(dados, usuario.empresa.nome),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                'attachment; filename="relatorio-avancado-vendas.xlsx"'
            )
        },
    )
