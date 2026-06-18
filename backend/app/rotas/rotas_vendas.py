from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.autenticacao.seguranca import obter_usuario_logado
from app.banco.conexao import obter_sessao_banco
from app.esquemas.venda import (
    CancelamentoVendaCriacao,
    CancelamentoVendaResposta,
    ItemVendaResposta,
    ProdutoVendaResposta,
    VendaCriacao,
    VendaFinanceiraResposta,
    VendaResposta,
    ResumoOperadorResposta,
    StatusPagamentoVendaResposta,
)
from app.modelos.usuario import Usuario
from app.servicos.servico_comprovante import gerar_comprovante_pdf
from app.servicos.servico_vendas import (
    buscar_produto_por_codigo,
    buscar_produtos_por_nome,
    buscar_venda_empresa,
    cancelar_venda,
    confirmar_pagamento_manual,
    consultar_status_pagamento,
    listar_vendas_financeiro,
    listar_vendas_recentes_operador,
    registrar_venda,
    resumir_vendas_por_operador,
)
from app.servicos.servico_permissoes import (
    garantir_permissao,
    garantir_uma_das_permissoes,
)
from app.servicos.servico_auditoria import registrar_auditoria


roteador_vendas = APIRouter(prefix="/vendas", tags=["Vendas"])


def montar_resposta_venda(venda, registros, qr_code=None) -> VendaResposta:
    itens = [
        ItemVendaResposta(
            produto_id=item.produto_id,
            nome_produto=item.nome_produto,
            codigo_barras=item.codigo_barras,
            quantidade=item.quantidade,
            valor_unitario=item.valor_unitario,
            valor_total=item.valor_total,
            quantidade_atual=produto.quantidade,
        )
        for item, produto in registros
    ]
    primeiro = itens[0]
    return VendaResposta(
        id=venda.id,
        itens=itens,
        subtotal=venda.subtotal,
        desconto=venda.desconto,
        valor_total=venda.valor_total,
        forma_pagamento=venda.forma_pagamento,
        valor_recebido=venda.valor_recebido,
        troco_entregue=venda.troco_entregue,
        status=venda.status,
        codigo_pix=venda.codigo_pix,
        qr_code_pix=qr_code,
        cobranca_externa_id=venda.cobranca_externa_id,
        status_cobranca=venda.status_cobranca,
        confirmacao_automatica=(
            venda.provedor_pagamento == "mercado_pago"
        ),
        data_venda=venda.data_venda,
        cliente_id=venda.cliente_id,
        nome_produto=primeiro.nome_produto,
        codigo_barras=primeiro.codigo_barras,
        quantidade=primeiro.quantidade,
        valor_unitario=primeiro.valor_unitario,
        quantidade_atual=primeiro.quantidade_atual,
    )


@roteador_vendas.get(
    "/produtos/pesquisa",
    response_model=list[ProdutoVendaResposta],
)
def pesquisar_produtos(
    nome: str = Query(min_length=2, max_length=180),
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "vendas_operar")
    return buscar_produtos_por_nome(nome, usuario, sessao)


@roteador_vendas.get(
    "/produto/{codigo_barras}",
    response_model=ProdutoVendaResposta,
)
def localizar_produto(
    codigo_barras: str,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "vendas_operar")
    return buscar_produto_por_codigo(codigo_barras, usuario, sessao)


@roteador_vendas.post(
    "",
    response_model=VendaResposta,
    status_code=status.HTTP_201_CREATED,
)
def criar_venda(
    dados: VendaCriacao,
    requisicao: Request,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "vendas_operar")
    venda, registros, qr_code = registrar_venda(
        dados,
        usuario,
        sessao,
        url_base_requisicao=str(requisicao.base_url).rstrip("/"),
    )
    return montar_resposta_venda(venda, registros, qr_code)


@roteador_vendas.post(
    "/{venda_id}/confirmar-pagamento",
    response_model=VendaResposta,
)
def confirmar_pagamento(
    venda_id: int,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "vendas_operar")
    venda, registros = confirmar_pagamento_manual(
        venda_id,
        usuario,
        sessao,
    )
    return montar_resposta_venda(venda, registros)


@roteador_vendas.get(
    "/{venda_id}/status-pagamento",
    response_model=StatusPagamentoVendaResposta,
)
def verificar_status_pagamento(
    venda_id: int,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "vendas_operar")
    return consultar_status_pagamento(venda_id, usuario, sessao)


@roteador_vendas.post(
    "/{venda_id}/cancelar",
    response_model=CancelamentoVendaResposta,
)
def estornar_venda(
    venda_id: int,
    dados: CancelamentoVendaCriacao,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "vendas_cancelar")
    return cancelar_venda(venda_id, dados, usuario, sessao)


@roteador_vendas.get(
    "/resumo-operadores",
    response_model=list[ResumoOperadorResposta],
)
def consultar_resumo_operadores(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "vendas_relatorios")
    return resumir_vendas_por_operador(usuario, sessao)


@roteador_vendas.get(
    "/recentes",
    response_model=list[VendaFinanceiraResposta],
)
def consultar_vendas_recentes(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "vendas_operar")
    return listar_vendas_recentes_operador(usuario, sessao)


@roteador_vendas.get("", response_model=list[VendaFinanceiraResposta])
def listar_vendas(
    usuario_id: int | None = None,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_uma_das_permissoes(
        usuario,
        "vendas_relatorios",
        "vendas_devolver",
    )
    return listar_vendas_financeiro(usuario, sessao, usuario_id)


@roteador_vendas.get("/{venda_id}/comprovante")
def baixar_comprovante(
    venda_id: int,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "vendas_operar")
    venda = buscar_venda_empresa(venda_id, usuario, sessao)
    if venda.status not in {"pago", "cancelado"}:
        raise HTTPException(
            409,
            "O comprovante fica disponivel apos a confirmacao do pagamento.",
        )
    arquivo = gerar_comprovante_pdf(venda, usuario.empresa.nome)
    registrar_auditoria(
        sessao,
        usuario,
        "comprovante_gerado",
        "venda",
        venda.id,
    )
    sessao.commit()
    return StreamingResponse(
        arquivo,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="comprovante-venda-{venda.id}.pdf"'
            )
        },
    )
