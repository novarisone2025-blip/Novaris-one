import io
from datetime import date, datetime, timezone
from decimal import Decimal
from urllib.parse import quote
from xml.sax.saxutils import escape

from fastapi import HTTPException
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.esquemas.orcamento import ConversaoOrcamento, OrcamentoCriacao
from app.esquemas.venda import ItemVendaCriacao, VendaCriacao
from app.modelos.cliente import Cliente
from app.modelos.comercial import ItemOrcamento, Orcamento
from app.modelos.empresa import Empresa
from app.modelos.produto import Produto
from app.modelos.usuario import Usuario
from app.servicos.servico_auditoria import registrar_auditoria
from app.servicos.servico_vendas import registrar_venda


def agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _buscar_orcamento(
    orcamento_id: int,
    usuario: Usuario,
    sessao: Session,
    bloquear: bool = False,
) -> Orcamento:
    consulta = (
        select(Orcamento)
        .options(
            selectinload(Orcamento.itens),
            selectinload(Orcamento.cliente),
        )
        .where(
            Orcamento.id == orcamento_id,
            Orcamento.empresa_id == usuario.empresa_id,
        )
    )
    if bloquear:
        consulta = consulta.with_for_update()
    orcamento = sessao.scalar(consulta)
    if not orcamento:
        raise HTTPException(404, "Orcamento nao encontrado.")
    return orcamento


def _serializar(orcamento: Orcamento, usuarios: dict[int, Usuario]) -> dict:
    cliente = orcamento.cliente
    return {
        "id": orcamento.id,
        "cliente_id": orcamento.cliente_id,
        "nome_cliente": cliente.nome if cliente else None,
        "cliente_documento": cliente.documento if cliente else None,
        "cliente_telefone": cliente.telefone if cliente else None,
        "cliente_whatsapp": cliente.whatsapp if cliente else None,
        "cliente_email": cliente.email if cliente else None,
        "cliente_endereco": cliente.endereco if cliente else None,
        "usuario_id": orcamento.usuario_id,
        "nome_usuario": usuarios[orcamento.usuario_id].nome,
        "venda_id": orcamento.venda_id,
        "status": orcamento.status,
        "subtotal": orcamento.subtotal,
        "desconto": orcamento.desconto,
        "valor_total": orcamento.valor_total,
        "observacoes": orcamento.observacoes,
        "validade": orcamento.validade,
        "data_criacao": orcamento.data_criacao,
        "data_conversao": orcamento.data_conversao,
        "itens": [
            {
                "id": item.id,
                "produto_id": item.produto_id,
                "nome_produto": item.nome_produto,
                "codigo_barras": item.codigo_barras,
                "quantidade": item.quantidade,
                "valor_unitario": item.valor_unitario,
                "desconto": item.desconto,
                "valor_total": item.valor_total,
            }
            for item in orcamento.itens
        ],
    }


def listar_orcamentos(
    usuario: Usuario,
    sessao: Session,
    status: str | None = None,
) -> list[dict]:
    consulta = (
        select(Orcamento)
        .options(
            selectinload(Orcamento.itens),
            selectinload(Orcamento.cliente),
        )
        .where(Orcamento.empresa_id == usuario.empresa_id)
        .order_by(Orcamento.data_criacao.desc())
    )
    if status:
        consulta = consulta.where(Orcamento.status == status)
    orcamentos = sessao.scalars(consulta).all()
    hoje = date.today()
    houve_expiracao = False
    for item in orcamentos:
        if item.status == "pendente" and item.validade < hoje:
            item.status = "expirado"
            houve_expiracao = True
    if houve_expiracao:
        sessao.commit()
    usuarios = {
        item.id: item for item in sessao.scalars(
            select(Usuario).where(Usuario.empresa_id == usuario.empresa_id)
        ).all()
    }
    return [_serializar(item, usuarios) for item in orcamentos]


def criar_orcamento(
    dados: OrcamentoCriacao,
    usuario: Usuario,
    sessao: Session,
) -> dict:
    if dados.validade < date.today():
        raise HTTPException(422, "A validade nao pode estar no passado.")
    cliente = None
    if dados.cliente_id:
        cliente = sessao.scalar(select(Cliente).where(
            Cliente.id == dados.cliente_id,
            Cliente.empresa_id == usuario.empresa_id,
            Cliente.ativo.is_(True),
        ))
        if not cliente:
            raise HTTPException(404, "Cliente nao encontrado.")
    ids = {item.produto_id for item in dados.itens}
    produtos = {
        produto.id: produto for produto in sessao.scalars(
            select(Produto).where(
                Produto.id.in_(ids),
                Produto.empresa_id == usuario.empresa_id,
                Produto.ativo.is_(True),
            )
        ).all()
    }
    if len(produtos) != len(ids):
        raise HTTPException(404, "Um ou mais produtos nao foram encontrados.")
    orcamento = Orcamento(
        empresa_id=usuario.empresa_id,
        cliente_id=cliente.id if cliente else None,
        usuario_id=usuario.id,
        validade=dados.validade,
        observacoes=(dados.observacoes or "").strip() or None,
    )
    sessao.add(orcamento)
    sessao.flush()
    subtotal = Decimal("0")
    for dados_item in dados.itens:
        produto = produtos[dados_item.produto_id]
        bruto = Decimal(produto.preco) * dados_item.quantidade
        desconto_item = Decimal(dados_item.desconto)
        if desconto_item > bruto:
            raise HTTPException(
                422,
                f"O desconto do produto {produto.nome} excede o subtotal.",
            )
        total_item = bruto - desconto_item
        subtotal += total_item
        sessao.add(ItemOrcamento(
            empresa_id=usuario.empresa_id,
            orcamento_id=orcamento.id,
            produto_id=produto.id,
            nome_produto=produto.nome,
            codigo_barras=produto.codigo_barras,
            quantidade=dados_item.quantidade,
            valor_unitario=produto.preco,
            desconto=desconto_item,
            valor_total=total_item,
        ))
    desconto = Decimal(dados.desconto)
    if desconto > subtotal:
        raise HTTPException(422, "O desconto geral excede o subtotal.")
    orcamento.subtotal = subtotal
    orcamento.desconto = desconto
    orcamento.valor_total = subtotal - desconto
    registrar_auditoria(
        sessao,
        usuario,
        "orcamento_criado",
        "orcamento",
        orcamento.id,
        {"cliente_id": orcamento.cliente_id, "valor_total": orcamento.valor_total},
    )
    sessao.commit()
    return next(
        item for item in listar_orcamentos(usuario, sessao)
        if item["id"] == orcamento.id
    )


def converter_orcamento(
    orcamento_id: int,
    dados: ConversaoOrcamento,
    usuario: Usuario,
    sessao: Session,
):
    orcamento = _buscar_orcamento(orcamento_id, usuario, sessao, bloquear=True)
    if orcamento.status != "pendente":
        raise HTTPException(409, "Somente orcamentos pendentes podem ser convertidos.")
    if orcamento.validade < date.today():
        orcamento.status = "expirado"
        sessao.commit()
        raise HTTPException(409, "Este orcamento esta expirado.")
    desconto_itens = sum(Decimal(item.desconto) for item in orcamento.itens)
    precos_cotados = {
        item.codigo_barras: Decimal(item.valor_unitario)
        for item in orcamento.itens
    }
    venda, registros, qr_code = registrar_venda(
        VendaCriacao(
            cliente_id=orcamento.cliente_id,
            itens=[
                ItemVendaCriacao(
                    codigo_barras=item.codigo_barras,
                    quantidade=item.quantidade,
                )
                for item in orcamento.itens
            ],
            desconto=Decimal(orcamento.desconto) + desconto_itens,
            forma_pagamento=dados.forma_pagamento,
        ),
        usuario,
        sessao,
        confirmar_transacao=False,
        precos_unitarios=precos_cotados,
    )
    orcamento.status = "convertido"
    orcamento.venda_id = venda.id
    orcamento.data_conversao = agora()
    registrar_auditoria(
        sessao,
        usuario,
        "orcamento_convertido",
        "orcamento",
        orcamento.id,
        {"venda_id": venda.id, "valor_total": venda.valor_total},
    )
    sessao.commit()
    return venda, registros, qr_code


def cancelar_orcamento(
    orcamento_id: int,
    usuario: Usuario,
    sessao: Session,
) -> dict:
    orcamento = _buscar_orcamento(orcamento_id, usuario, sessao, bloquear=True)
    if orcamento.status != "pendente":
        raise HTTPException(409, "Somente orcamentos pendentes podem ser cancelados.")
    orcamento.status = "cancelado"
    registrar_auditoria(
        sessao,
        usuario,
        "orcamento_cancelado",
        "orcamento",
        orcamento.id,
    )
    sessao.commit()
    return next(
        item for item in listar_orcamentos(usuario, sessao)
        if item["id"] == orcamento.id
    )


def gerar_pdf_orcamento(
    orcamento: Orcamento,
    empresa: Empresa,
) -> io.BytesIO:
    arquivo = io.BytesIO()
    documento = SimpleDocTemplate(
        arquivo,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    estilos = getSampleStyleSheet()
    roxo = colors.HexColor("#6552E8")
    roxo_escuro = colors.HexColor("#2A2146")
    cinza = colors.HexColor("#6F6C7D")
    linha = colors.HexColor("#E5E2EE")
    fundo_suave = colors.HexColor("#F7F5FC")
    cliente = orcamento.cliente

    estilo_titulo = ParagraphStyle(
        "TituloOrcamento",
        parent=estilos["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=21,
        textColor=roxo_escuro,
        alignment=TA_RIGHT,
        spaceAfter=2,
    )
    estilo_rotulo = ParagraphStyle(
        "RotuloOrcamento",
        parent=estilos["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        textColor=roxo,
    )
    estilo_rotulo_tabela = ParagraphStyle(
        "RotuloTabelaOrcamento",
        parent=estilo_rotulo,
        textColor=colors.white,
    )
    estilo_texto = ParagraphStyle(
        "TextoOrcamento",
        parent=estilos["Normal"],
        fontSize=8.5,
        leading=12,
        textColor=roxo_escuro,
    )
    estilo_texto_suave = ParagraphStyle(
        "TextoSuaveOrcamento",
        parent=estilo_texto,
        textColor=cinza,
    )
    estilo_tabela = ParagraphStyle(
        "TabelaOrcamento",
        parent=estilo_texto,
        fontSize=7.5,
        leading=9,
    )

    palavras_empresa = [
        palavra for palavra in empresa.nome.strip().split() if palavra
    ]
    iniciais = "".join(palavra[0] for palavra in palavras_empresa[:2]).upper()
    iniciais = iniciais or "N"
    logotipo = Drawing(17 * mm, 17 * mm)
    logotipo.add(Rect(
        0,
        0,
        17 * mm,
        17 * mm,
        rx=4 * mm,
        ry=4 * mm,
        fillColor=roxo,
        strokeColor=None,
    ))
    logotipo.add(String(
        8.5 * mm,
        5.7 * mm,
        iniciais,
        textAnchor="middle",
        fontName="Helvetica-Bold",
        fontSize=15,
        fillColor=colors.white,
    ))
    dados_empresa = [f"<b>{escape(empresa.nome)}</b>"]
    if empresa.cnpj:
        dados_empresa.append(f"CNPJ: {escape(empresa.cnpj)}")
    if empresa.telefone:
        dados_empresa.append(f"Telefone: {escape(empresa.telefone)}")
    cabecalho = Table(
        [[
            logotipo,
            Paragraph("<br/>".join(dados_empresa), estilo_texto),
            Paragraph(
                f"ORÇAMENTO<br/><font size='9' color='#6F6C7D'>"
                f"Proposta #{orcamento.id:05d}</font>",
                estilo_titulo,
            ),
        ]],
        colWidths=[21 * mm, 85 * mm, 68 * mm],
    )
    cabecalho.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    nome_cliente = cliente.nome if cliente else "Consumidor nao identificado"
    contato_cliente = "Nao informado"
    if cliente:
        contato_cliente = (
            cliente.whatsapp
            or cliente.telefone
            or cliente.email
            or "Nao informado"
        )
    dados_cliente = [
        [
            Paragraph("CLIENTE", estilo_rotulo),
            Paragraph("DOCUMENTO", estilo_rotulo),
            Paragraph("CONTATO", estilo_rotulo),
        ],
        [
            Paragraph(escape(nome_cliente), estilo_texto),
            Paragraph(
                escape(cliente.documento if cliente and cliente.documento else "-"),
                estilo_texto,
            ),
            Paragraph(escape(contato_cliente), estilo_texto),
        ],
        [
            Paragraph("ENDERECO", estilo_rotulo),
            Paragraph("EMISSAO", estilo_rotulo),
            Paragraph("VALIDADE", estilo_rotulo),
        ],
        [
            Paragraph(
                escape(cliente.endereco if cliente and cliente.endereco else "-"),
                estilo_texto,
            ),
            Paragraph(
                orcamento.data_criacao.strftime("%d/%m/%Y"),
                estilo_texto,
            ),
            Paragraph(
                orcamento.validade.strftime("%d/%m/%Y"),
                estilo_texto,
            ),
        ],
    ]
    quadro_cliente = Table(
        dados_cliente,
        colWidths=[76 * mm, 44 * mm, 54 * mm],
    )
    quadro_cliente.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fundo_suave),
        ("BOX", (0, 0), (-1, -1), .6, linha),
        ("LINEBELOW", (0, 1), (-1, 1), .4, linha),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    linhas = [[
        Paragraph("PRODUTO", estilo_rotulo_tabela),
        Paragraph("CÓDIGO", estilo_rotulo_tabela),
        Paragraph("QTD.", estilo_rotulo_tabela),
        Paragraph("VALOR UNIT.", estilo_rotulo_tabela),
        Paragraph("SUBTOTAL", estilo_rotulo_tabela),
    ]]
    for item in orcamento.itens:
        linhas.append([
            Paragraph(escape(item.nome_produto), estilo_tabela),
            Paragraph(escape(item.codigo_barras), estilo_tabela),
            Paragraph(str(item.quantidade), estilo_tabela),
            Paragraph(
                _formatar_moeda(Decimal(item.valor_unitario)),
                estilo_tabela,
            ),
            Paragraph(
                _formatar_moeda(Decimal(item.valor_total)),
                estilo_tabela,
            ),
        ])
    tabela = Table(
        linhas,
        colWidths=[70 * mm, 33 * mm, 14 * mm, 28 * mm, 29 * mm],
        repeatRows=1,
    )
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), roxo),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, fundo_suave]),
        ("LINEBELOW", (0, 0), (-1, -1), .35, linha),
        ("BOX", (0, 0), (-1, -1), .45, linha),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
    ]))
    totais = Table(
        [
            [
                Paragraph("Subtotal dos itens", estilo_texto_suave),
                Paragraph(
                    _formatar_moeda(Decimal(orcamento.subtotal)),
                    estilo_texto,
                ),
            ],
            [
                Paragraph("Desconto geral", estilo_texto_suave),
                Paragraph(
                    f"- {_formatar_moeda(Decimal(orcamento.desconto))}",
                    estilo_texto,
                ),
            ],
            [
                Paragraph("<b>VALOR TOTAL</b>", estilo_texto),
                Paragraph(
                    f"<b>{_formatar_moeda(Decimal(orcamento.valor_total))}</b>",
                    ParagraphStyle(
                        "TotalOrcamento",
                        parent=estilo_texto,
                        fontSize=12,
                        leading=14,
                        alignment=TA_RIGHT,
                        textColor=roxo,
                    ),
                ),
            ],
        ],
        colWidths=[42 * mm, 36 * mm],
        hAlign="RIGHT",
    )
    totais.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, 2), (-1, 2), .8, roxo),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    elementos = [
        cabecalho,
        Spacer(1, 8 * mm),
        quadro_cliente,
        Spacer(1, 7 * mm),
        tabela,
        Spacer(1, 5 * mm),
        totais,
    ]
    if orcamento.observacoes:
        elementos.extend([
            Spacer(1, 7 * mm),
            KeepTogether([
                Paragraph("OBSERVAÇÕES", estilo_rotulo),
                Spacer(1, 2 * mm),
                Table(
                    [[Paragraph(
                        escape(orcamento.observacoes).replace("\n", "<br/>"),
                        estilo_texto,
                    )]],
                    colWidths=[174 * mm],
                    style=TableStyle([
                        ("BACKGROUND", (0, 0), (-1, -1), fundo_suave),
                        ("BOX", (0, 0), (-1, -1), .5, linha),
                        ("PADDING", (0, 0), (-1, -1), 8),
                    ]),
                ),
            ]),
        ])
    elementos.extend([
        Spacer(1, 12 * mm),
        Paragraph(
            "Esta proposta está sujeita à disponibilidade de estoque no "
            "momento da conversão em venda.",
            ParagraphStyle(
                "AvisoOrcamento",
                parent=estilo_texto_suave,
                fontSize=7.5,
                alignment=TA_CENTER,
            ),
        ),
    ])

    def desenhar_rodape(canvas, doc):
        canvas.saveState()
        largura, _ = A4
        canvas.setStrokeColor(linha)
        canvas.line(18 * mm, 11 * mm, largura - 18 * mm, 11 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(cinza)
        canvas.drawString(
            18 * mm,
            7 * mm,
            "Documento gerado pelo Novaris One",
        )
        canvas.drawRightString(
            largura - 18 * mm,
            7 * mm,
            f"Página {doc.page}",
        )
        canvas.restoreState()

    documento.build(
        elementos,
        onFirstPage=desenhar_rodape,
        onLaterPages=desenhar_rodape,
    )
    arquivo.seek(0)
    return arquivo


def _formatar_moeda(valor: Decimal) -> str:
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}"


def links_compartilhamento(orcamento: Orcamento, nome_empresa: str) -> dict:
    cliente = orcamento.cliente
    saudacao = f"Olá, {cliente.nome}!" if cliente else "Olá!"
    itens = "\n".join(
        f"- {item.quantidade}x {item.nome_produto}: "
        f"{_formatar_moeda(Decimal(item.valor_total))}"
        for item in orcamento.itens
    )
    mensagem = (
        f"{saudacao}\n\n"
        f"Segue o orçamento #{orcamento.id:05d} da {nome_empresa}.\n\n"
        f"{itens}\n\n"
        f"Valor total: {_formatar_moeda(Decimal(orcamento.valor_total))}\n"
        f"Válido até: {orcamento.validade.strftime('%d/%m/%Y')}\n\n"
        "O PDF completo pode ser baixado pelo Novaris One."
    )
    telefone = "".join(
        caractere for caractere in ((cliente.whatsapp if cliente else "") or "")
        if caractere.isdigit()
    )
    destino_email = cliente.email if cliente and cliente.email else ""
    return {
        "whatsapp_url": (
            f"https://wa.me/{telefone}?text={quote(mensagem)}"
            if telefone else f"https://wa.me/?text={quote(mensagem)}"
        ),
        "email_url": (
            f"mailto:{destino_email}?subject={quote(f'Orçamento #{orcamento.id} - {nome_empresa}')}"
            f"&body={quote(mensagem)}"
        ),
    }
