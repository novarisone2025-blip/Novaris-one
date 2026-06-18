from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.autenticacao.seguranca import obter_usuario_logado
from app.banco.conexao import obter_sessao_banco
from app.esquemas.estoque import (
    MovimentacaoCriacao,
    MovimentacaoResposta,
    AlertaEstoqueResposta,
    ProdutoAtualizacao,
    ProdutoCriacao,
    ProdutoResposta,
    ResultadoMovimentacao,
)
from app.modelos.usuario import Usuario
from app.servicos.servico_estoque import (
    atualizar_produto,
    cadastrar_produto,
    excluir_produto,
    listar_produtos_empresa,
    listar_movimentacoes,
    listar_alertas_estoque,
    movimentar_estoque,
)
from app.servicos.servico_relatorios import (
    gerar_relatorio_excel,
    gerar_relatorio_pdf,
)
from app.servicos.servico_auditoria import registrar_auditoria
from app.servicos.servico_permissoes import (
    garantir_permissao,
    garantir_uma_das_permissoes,
    garantir_visualizacao_alertas_estoque,
)


roteador_estoque = APIRouter(
    prefix="/estoque",
    tags=["Estoque"],
)


@roteador_estoque.get(
    "/produtos",
    response_model=list[ProdutoResposta],
    summary="Listar produtos",
)
def listar_produtos(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "estoque_visualizar")
    return listar_produtos_empresa(usuario, sessao)


@roteador_estoque.post(
    "/produtos",
    response_model=ProdutoResposta,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar produto",
)
def criar_produto(
    dados: ProdutoCriacao,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_uma_das_permissoes(
        usuario,
        "estoque_gerenciar",
        "produtos_cadastrar",
    )
    return cadastrar_produto(dados, usuario, sessao)


@roteador_estoque.put(
    "/produtos/{produto_id}",
    response_model=ProdutoResposta,
    summary="Atualizar produto",
)
def editar_produto(
    produto_id: int,
    dados: ProdutoAtualizacao,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_uma_das_permissoes(
        usuario,
        "estoque_gerenciar",
        "produtos_editar",
    )
    return atualizar_produto(produto_id, dados, usuario, sessao)


@roteador_estoque.post(
    "/produtos/{produto_id}/movimentacoes",
    response_model=ResultadoMovimentacao,
    summary="Registrar entrada ou venda",
)
def registrar_movimentacao(
    produto_id: int,
    dados: MovimentacaoCriacao,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "estoque_movimentar")
    produto = movimentar_estoque(produto_id, dados, usuario, sessao)
    acao = "Entrada registrada" if dados.tipo == "entrada" else "Saída registrada"
    return ResultadoMovimentacao(
        mensagem=f"{acao} com sucesso.",
        quantidade_atual=produto.quantidade,
    )


@roteador_estoque.delete(
    "/produtos/{produto_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir produto",
)
def remover_produto(
    produto_id: int,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_uma_das_permissoes(
        usuario,
        "estoque_gerenciar",
        "produtos_excluir",
    )
    excluir_produto(produto_id, usuario, sessao)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@roteador_estoque.get(
    "/movimentacoes",
    response_model=list[MovimentacaoResposta],
    summary="Consultar histórico de estoque",
)
def consultar_historico(
    busca: str = Query(default="", max_length=180),
    tipo: str | None = Query(default=None, pattern="^(entrada|saida)$"),
    data_inicial: date | None = None,
    data_final: date | None = None,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "estoque_visualizar")
    return listar_movimentacoes(
        usuario,
        sessao,
        busca,
        tipo,
        data_inicial,
        data_final,
    )


@roteador_estoque.get(
    "/alertas",
    response_model=list[AlertaEstoqueResposta],
    summary="Listar produtos com estoque baixo",
)
def consultar_alertas(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "estoque_visualizar")
    garantir_visualizacao_alertas_estoque(usuario)
    return listar_alertas_estoque(usuario, sessao)


@roteador_estoque.get("/relatorios/pdf", summary="Baixar relatório PDF")
def baixar_relatorio_pdf(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "relatorios_gerar")
    produtos = listar_produtos_empresa(usuario, sessao)
    arquivo = gerar_relatorio_pdf(produtos, usuario.empresa.nome)
    registrar_auditoria(
        sessao,
        usuario,
        "relatorio_gerado",
        "estoque",
        detalhes={"formato": "pdf"},
    )
    sessao.commit()
    return StreamingResponse(
        arquivo,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="relatorio-estoque.pdf"'
        },
    )


@roteador_estoque.get("/relatorios/excel", summary="Baixar relatório Excel")
def baixar_relatorio_excel(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "relatorios_gerar")
    produtos = listar_produtos_empresa(usuario, sessao)
    arquivo = gerar_relatorio_excel(produtos, usuario.empresa.nome)
    registrar_auditoria(
        sessao,
        usuario,
        "relatorio_gerado",
        "estoque",
        detalhes={"formato": "excel"},
    )
    sessao.commit()
    return StreamingResponse(
        arquivo,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": 'attachment; filename="relatorio-estoque.xlsx"'
        },
    )
