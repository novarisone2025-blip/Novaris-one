from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.autenticacao.seguranca import obter_usuario_logado
from app.banco.conexao import obter_sessao_banco
from app.esquemas.cliente import (
    ClienteAtualizacao,
    ClienteCriacao,
    ClienteDetalhe,
    ClienteResposta,
)
from app.modelos.usuario import Usuario
from app.servicos.servico_auditoria import registrar_auditoria
from app.servicos.servico_clientes import (
    detalhar_cliente,
    gerar_relatorio_clientes_excel,
    gerar_relatorio_clientes_pdf,
    listar_clientes,
    salvar_cliente,
    serializar_cliente,
)
from app.servicos.servico_permissoes import garantir_permissao


roteador_clientes = APIRouter(prefix="/clientes", tags=["Clientes"])


@roteador_clientes.get("", response_model=list[ClienteResposta])
def consultar_clientes(
    busca: str = Query(default="", max_length=180),
    somente_ativos: bool = True,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "clientes_visualizar")
    return listar_clientes(usuario, sessao, busca, somente_ativos)


@roteador_clientes.post(
    "",
    response_model=ClienteResposta,
    status_code=status.HTTP_201_CREATED,
)
def criar_cliente(
    dados: ClienteCriacao,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "clientes_gerenciar")
    return serializar_cliente(salvar_cliente(dados, usuario, sessao))


@roteador_clientes.put("/{cliente_id}", response_model=ClienteResposta)
def atualizar_cliente(
    cliente_id: int,
    dados: ClienteAtualizacao,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "clientes_gerenciar")
    return serializar_cliente(
        salvar_cliente(dados, usuario, sessao, cliente_id)
    )


@roteador_clientes.get("/{cliente_id}", response_model=ClienteDetalhe)
def consultar_cliente(
    cliente_id: int,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "clientes_visualizar")
    return detalhar_cliente(cliente_id, usuario, sessao)


@roteador_clientes.get("/relatorios/pdf/arquivo")
def baixar_clientes_pdf(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "clientes_relatorios")
    arquivo = gerar_relatorio_clientes_pdf(
        listar_clientes(usuario, sessao, somente_ativos=False),
        usuario.empresa.nome,
    )
    registrar_auditoria(
        sessao, usuario, "relatorio_clientes_gerado", "clientes",
        detalhes={"formato": "pdf"},
    )
    sessao.commit()
    return StreamingResponse(
        arquivo,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="clientes.pdf"'},
    )


@roteador_clientes.get("/relatorios/excel/arquivo")
def baixar_clientes_excel(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "clientes_relatorios")
    arquivo = gerar_relatorio_clientes_excel(
        listar_clientes(usuario, sessao, somente_ativos=False),
        usuario.empresa.nome,
    )
    registrar_auditoria(
        sessao, usuario, "relatorio_clientes_gerado", "clientes",
        detalhes={"formato": "excel"},
    )
    sessao.commit()
    return StreamingResponse(
        arquivo,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": 'attachment; filename="clientes.xlsx"'},
    )
