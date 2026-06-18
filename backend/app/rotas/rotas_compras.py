from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.autenticacao.seguranca import obter_usuario_logado
from app.banco.conexao import obter_sessao_banco
from app.esquemas.compra import (
    PedidoCompraCriacao,
    PedidoCompraResposta,
    PedidoCompraStatus,
    SugestaoReposicaoResposta,
)
from app.modelos.usuario import Usuario
from app.servicos.servico_compras import (
    atualizar_status_pedido,
    criar_pedido,
    listar_pedidos,
    listar_sugestoes_reposicao,
)
from app.servicos.servico_permissoes import garantir_permissao


roteador_compras = APIRouter(prefix="/compras", tags=["Compras"])


@roteador_compras.get(
    "/sugestoes",
    response_model=list[SugestaoReposicaoResposta],
)
def consultar_sugestoes(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "compras_visualizar")
    return listar_sugestoes_reposicao(usuario, sessao)


@roteador_compras.get("", response_model=list[PedidoCompraResposta])
def consultar_pedidos(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "compras_visualizar")
    return listar_pedidos(usuario, sessao)


@roteador_compras.post(
    "",
    response_model=PedidoCompraResposta,
    status_code=status.HTTP_201_CREATED,
)
def registrar_pedido(
    dados: PedidoCompraCriacao,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "compras_gerenciar")
    return criar_pedido(dados, usuario, sessao)


@roteador_compras.patch(
    "/{pedido_id}/status",
    response_model=PedidoCompraResposta,
)
def alterar_status_pedido(
    pedido_id: int,
    dados: PedidoCompraStatus,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "compras_gerenciar")
    return atualizar_status_pedido(
        pedido_id,
        dados.status,
        usuario,
        sessao,
    )
