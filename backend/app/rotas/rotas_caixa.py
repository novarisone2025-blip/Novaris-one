from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.autenticacao.seguranca import obter_usuario_logado
from app.banco.conexao import obter_sessao_banco
from app.esquemas.caixa import (
    AberturaCaixa,
    CaixaResposta,
    FechamentoCaixa,
    MovimentacaoCaixaCriacao,
    MovimentacaoCaixaResposta,
)
from app.modelos.usuario import Usuario
from app.servicos.servico_caixa import (
    abrir_caixa,
    buscar_caixa_empresa,
    fechar_caixa,
    listar_caixas_ativos,
    montar_resposta_caixa,
    obter_caixa_aberto,
    registrar_movimentacao_caixa,
)
from app.servicos.servico_permissoes import garantir_permissao
from app.servicos.servico_permissoes import permissoes_do_usuario
from app.servicos.servico_relatorio_caixa import gerar_relatorio_fechamento


roteador_caixa = APIRouter(prefix="/caixa", tags=["Caixa"])


@roteador_caixa.get("/atual", response_model=CaixaResposta | None)
def consultar_caixa_atual(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "vendas_operar")
    caixa = obter_caixa_aberto(usuario, sessao)
    return (
        montar_resposta_caixa(caixa, usuario, sessao)
        if caixa
        else None
    )


@roteador_caixa.post("/abrir", response_model=CaixaResposta)
def iniciar_caixa(
    dados: AberturaCaixa,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "vendas_operar")
    return abrir_caixa(dados, usuario, sessao)


@roteador_caixa.post("/fechar", response_model=CaixaResposta)
def concluir_caixa(
    dados: FechamentoCaixa,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "vendas_operar")
    return fechar_caixa(dados, usuario, sessao)


@roteador_caixa.post(
    "/sangria",
    response_model=MovimentacaoCaixaResposta,
)
def realizar_sangria(
    dados: MovimentacaoCaixaCriacao,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "caixa_sangria")
    return registrar_movimentacao_caixa("sangria", dados, usuario, sessao)


@roteador_caixa.post(
    "/reforco",
    response_model=MovimentacaoCaixaResposta,
)
def realizar_reforco(
    dados: MovimentacaoCaixaCriacao,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "caixa_reforco")
    return registrar_movimentacao_caixa("reforco", dados, usuario, sessao)


@roteador_caixa.get("/ativos", response_model=list[CaixaResposta])
def consultar_caixas_ativos(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "caixas_ativos_visualizar")
    return listar_caixas_ativos(usuario, sessao)


@roteador_caixa.get("/{caixa_id}/relatorio")
def baixar_relatorio_caixa(
    caixa_id: int,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "vendas_operar")
    caixa, responsavel = buscar_caixa_empresa(caixa_id, usuario, sessao)
    if (
        caixa.usuario_id != usuario.id
        and "vendas_relatorios" not in permissoes_do_usuario(usuario)
    ):
        from fastapi import HTTPException
        raise HTTPException(403, "Voce nao pode acessar o caixa de outro usuario.")
    if caixa.status != "fechado":
        from fastapi import HTTPException
        raise HTTPException(409, "Feche o caixa antes de gerar o relatorio.")
    dados = montar_resposta_caixa(caixa, responsavel, sessao)
    arquivo = gerar_relatorio_fechamento(dados, usuario.empresa.nome)
    return StreamingResponse(
        arquivo,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="fechamento-caixa-{caixa.id}.pdf"'
            )
        },
    )
