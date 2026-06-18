from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.autenticacao.seguranca import obter_usuario_logado
from app.banco.conexao import obter_sessao_banco
from app.esquemas.operacoes import (
    DevolucaoVendaCriacao,
    DevolucaoVendaResposta,
    VendaParaDevolucaoResposta,
)
from app.modelos.usuario import Usuario
from app.servicos.servico_operacoes import (
    detalhar_venda_para_devolucao,
    listar_devolucoes,
    registrar_devolucao_ou_troca,
)
from app.servicos.servico_permissoes import garantir_permissao


roteador_operacoes = APIRouter(
    prefix="/operacoes-venda",
    tags=["Trocas e devolucoes"],
)


@roteador_operacoes.get(
    "/vendas/{venda_id}",
    response_model=VendaParaDevolucaoResposta,
)
def consultar_venda(
    venda_id: int,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "vendas_devolver")
    return detalhar_venda_para_devolucao(venda_id, usuario, sessao)


@roteador_operacoes.post(
    "/vendas/{venda_id}",
    response_model=DevolucaoVendaResposta,
    status_code=status.HTTP_201_CREATED,
)
def realizar_operacao(
    venda_id: int,
    dados: DevolucaoVendaCriacao,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "vendas_devolver")
    return registrar_devolucao_ou_troca(venda_id, dados, usuario, sessao)


@roteador_operacoes.get(
    "",
    response_model=list[DevolucaoVendaResposta],
)
def consultar_operacoes(
    venda_id: int | None = None,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "vendas_devolver")
    return listar_devolucoes(usuario, sessao, venda_id)
