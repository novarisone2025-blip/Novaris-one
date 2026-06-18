from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.autenticacao.seguranca import obter_usuario_logado
from app.banco.conexao import obter_sessao_banco
from app.esquemas.orcamento import (
    CompartilhamentoOrcamento,
    ConversaoOrcamento,
    OrcamentoCriacao,
    OrcamentoResposta,
)
from app.esquemas.venda import VendaResposta
from app.modelos.usuario import Usuario
from app.rotas.rotas_vendas import montar_resposta_venda
from app.servicos.servico_auditoria import registrar_auditoria
from app.servicos.servico_orcamentos import (
    _buscar_orcamento,
    cancelar_orcamento,
    converter_orcamento,
    criar_orcamento,
    gerar_pdf_orcamento,
    links_compartilhamento,
    listar_orcamentos,
)
from app.servicos.servico_permissoes import garantir_permissao


roteador_orcamentos = APIRouter(prefix="/orcamentos", tags=["Orcamentos"])


@roteador_orcamentos.get("", response_model=list[OrcamentoResposta])
def consultar_orcamentos(
    status_orcamento: str | None = Query(default=None, alias="status"),
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "orcamentos_visualizar")
    return listar_orcamentos(usuario, sessao, status_orcamento)


@roteador_orcamentos.post(
    "",
    response_model=OrcamentoResposta,
    status_code=status.HTTP_201_CREATED,
)
def registrar_orcamento(
    dados: OrcamentoCriacao,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "orcamentos_gerenciar")
    return criar_orcamento(dados, usuario, sessao)


@roteador_orcamentos.post("/{orcamento_id}/converter", response_model=VendaResposta)
def transformar_em_venda(
    orcamento_id: int,
    dados: ConversaoOrcamento,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "orcamentos_converter")
    venda, registros, qr_code = converter_orcamento(
        orcamento_id,
        dados,
        usuario,
        sessao,
    )
    return montar_resposta_venda(venda, registros, qr_code)


@roteador_orcamentos.post(
    "/{orcamento_id}/cancelar",
    response_model=OrcamentoResposta,
)
def cancelar(
    orcamento_id: int,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "orcamentos_gerenciar")
    return cancelar_orcamento(orcamento_id, usuario, sessao)


@roteador_orcamentos.get("/{orcamento_id}/pdf")
def baixar_pdf(
    orcamento_id: int,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "orcamentos_visualizar")
    orcamento = _buscar_orcamento(orcamento_id, usuario, sessao)
    arquivo = gerar_pdf_orcamento(orcamento, usuario.empresa)
    registrar_auditoria(
        sessao,
        usuario,
        "orcamento_pdf_gerado",
        "orcamento",
        orcamento.id,
    )
    sessao.commit()
    return StreamingResponse(
        arquivo,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="orcamento-{orcamento.id}.pdf"'
            )
        },
    )


@roteador_orcamentos.get(
    "/{orcamento_id}/compartilhar",
    response_model=CompartilhamentoOrcamento,
)
def compartilhar(
    orcamento_id: int,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "orcamentos_visualizar")
    orcamento = _buscar_orcamento(orcamento_id, usuario, sessao)
    registrar_auditoria(
        sessao,
        usuario,
        "orcamento_compartilhado",
        "orcamento",
        orcamento.id,
    )
    sessao.commit()
    return links_compartilhamento(orcamento, usuario.empresa.nome)
