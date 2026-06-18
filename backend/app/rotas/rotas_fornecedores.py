from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.autenticacao.seguranca import obter_usuario_logado
from app.banco.conexao import obter_sessao_banco
from app.esquemas.fornecedor import FornecedorCriacao, FornecedorResposta
from app.modelos.usuario import Usuario
from app.servicos.servico_fornecedores import (
    excluir_fornecedor,
    listar_fornecedores,
    salvar_fornecedor,
)
from app.servicos.servico_permissoes import garantir_permissao


roteador_fornecedores = APIRouter(
    prefix="/fornecedores",
    tags=["Fornecedores"],
)


@roteador_fornecedores.get("", response_model=list[FornecedorResposta])
def consultar_fornecedores(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "estoque_visualizar")
    return listar_fornecedores(usuario, sessao)


@roteador_fornecedores.post(
    "",
    response_model=FornecedorResposta,
    status_code=status.HTTP_201_CREATED,
)
def criar_fornecedor(
    dados: FornecedorCriacao,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "fornecedores_gerenciar")
    fornecedor = salvar_fornecedor(dados, usuario, sessao)
    return {**fornecedor.__dict__, "total_produtos": 0}


@roteador_fornecedores.put(
    "/{fornecedor_id}",
    response_model=FornecedorResposta,
)
def atualizar_fornecedor(
    fornecedor_id: int,
    dados: FornecedorCriacao,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "fornecedores_gerenciar")
    fornecedor = salvar_fornecedor(
        dados,
        usuario,
        sessao,
        fornecedor_id,
    )
    return {
        **fornecedor.__dict__,
        "total_produtos": len(fornecedor.produtos),
    }


@roteador_fornecedores.delete(
    "/{fornecedor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remover_fornecedor(
    fornecedor_id: int,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "fornecedores_gerenciar")
    excluir_fornecedor(fornecedor_id, usuario, sessao)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
