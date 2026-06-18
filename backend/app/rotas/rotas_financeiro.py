from datetime import date

from fastapi import APIRouter, Depends, Path, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.autenticacao.seguranca import obter_usuario_logado
from app.banco.conexao import obter_sessao_banco
from app.esquemas.financeiro import (
    LancamentoCriacao,
    LancamentoResposta,
    ResumoFinanceiroResposta,
)
from app.modelos.usuario import Usuario
from app.servicos.servico_financeiro import (
    calcular_resumo_financeiro,
    criar_lancamento,
    gerar_relatorio_financeiro_excel,
    gerar_relatorio_financeiro_pdf,
    listar_fluxo_caixa,
)
from app.servicos.servico_auditoria import registrar_auditoria
from app.servicos.servico_permissoes import garantir_permissao


roteador_financeiro = APIRouter(
    prefix="/financeiro",
    tags=["Financeiro"],
)


@roteador_financeiro.get(
    "/resumo",
    response_model=ResumoFinanceiroResposta,
)
def consultar_resumo(
    data_inicial: date | None = None,
    data_final: date | None = None,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "financeiro_visualizar")
    return calcular_resumo_financeiro(
        usuario,
        sessao,
        data_inicial,
        data_final,
    )


@roteador_financeiro.get(
    "/fluxo-caixa",
    response_model=list[LancamentoResposta],
)
def consultar_fluxo(
    data_inicial: date | None = None,
    data_final: date | None = None,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "financeiro_visualizar")
    return listar_fluxo_caixa(usuario, sessao, data_inicial, data_final)


@roteador_financeiro.post(
    "/lancamentos",
    response_model=LancamentoResposta,
    status_code=status.HTTP_201_CREATED,
)
def registrar_lancamento(
    dados: LancamentoCriacao,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "financeiro_lancar")
    lancamento = criar_lancamento(dados, usuario, sessao)
    return {
        **lancamento.__dict__,
        "origem": "manual",
        "nome_usuario": usuario.nome,
        "cargo_usuario": usuario.cargo,
        "caixa_id": None,
    }


@roteador_financeiro.get("/relatorios/{formato}")
def baixar_relatorio(
    formato: str = Path(pattern="^(pdf|excel)$"),
    data_inicial: date | None = None,
    data_final: date | None = None,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "relatorios_gerar")
    resumo = calcular_resumo_financeiro(
        usuario,
        sessao,
        data_inicial,
        data_final,
    )
    fluxo = listar_fluxo_caixa(
        usuario,
        sessao,
        data_inicial,
        data_final,
    )
    registrar_auditoria(
        sessao,
        usuario,
        "relatorio_gerado",
        "financeiro",
        detalhes={"formato": formato},
    )
    sessao.commit()
    if formato == "pdf":
        arquivo = gerar_relatorio_financeiro_pdf(
            resumo,
            fluxo,
            usuario.empresa.nome,
        )
        return StreamingResponse(
            arquivo,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    'attachment; filename="relatorio-financeiro.pdf"'
                )
            },
        )
    arquivo = gerar_relatorio_financeiro_excel(
        resumo,
        fluxo,
        usuario.empresa.nome,
    )
    return StreamingResponse(
        arquivo,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                'attachment; filename="relatorio-financeiro.xlsx"'
            )
        },
    )
