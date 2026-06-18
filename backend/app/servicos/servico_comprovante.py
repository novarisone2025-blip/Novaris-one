import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modelos.venda import Venda
from app.servicos.servico_relatorios import formatar_moeda


NOMES_PAGAMENTO = {
    "dinheiro": "Dinheiro",
    "pix": "Pix",
    "debito": "Cartao de debito",
    "credito": "Cartao de credito",
}


def gerar_comprovante_pdf(venda: Venda, nome_empresa: str) -> io.BytesIO:
    arquivo = io.BytesIO()
    documento = SimpleDocTemplate(
        arquivo,
        pagesize=A4,
        rightMargin=24 * mm,
        leftMargin=24 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    estilos = getSampleStyleSheet()
    elementos = [
        Paragraph(f"<b>{nome_empresa}</b>", estilos["Title"]),
        Paragraph(
            f"Comprovante da venda #{venda.id}",
            estilos["Heading2"],
        ),
        Paragraph(
            venda.data_venda.strftime("%d/%m/%Y as %H:%M"),
            estilos["Normal"],
        ),
        Spacer(1, 14),
    ]
    linhas = [["Produto", "Qtd.", "Unitario", "Total"]]
    for item in venda.itens:
        linhas.append([
            item.nome_produto,
            str(item.quantidade),
            formatar_moeda(item.valor_unitario),
            formatar_moeda(item.valor_total),
        ])
    tabela = Table(linhas, colWidths=[85 * mm, 18 * mm, 32 * mm, 32 * mm])
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#6E5CF5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9D7E3")),
        ("PADDING", (0, 0), (-1, -1), 7),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]))
    elementos.extend([
        tabela,
        Spacer(1, 15),
        Paragraph(f"Subtotal: <b>{formatar_moeda(venda.subtotal)}</b>", estilos["Normal"]),
        Paragraph(f"Desconto: <b>{formatar_moeda(venda.desconto)}</b>", estilos["Normal"]),
        Paragraph(f"Total: <b>{formatar_moeda(venda.valor_total)}</b>", estilos["Heading2"]),
        Paragraph(
            "Pagamento: "
            f"<b>{NOMES_PAGAMENTO.get(venda.forma_pagamento, venda.forma_pagamento)}</b>",
            estilos["Normal"],
        ),
        *(
            [
                Paragraph(
                    "Valor recebido: "
                    f"<b>{formatar_moeda(venda.valor_recebido)}</b>",
                    estilos["Normal"],
                ),
                Paragraph(
                    "Troco entregue: "
                    f"<b>{formatar_moeda(venda.troco_entregue)}</b>",
                    estilos["Normal"],
                ),
            ]
            if venda.forma_pagamento == "dinheiro"
            else []
        ),
        Spacer(1, 20),
        Paragraph("Obrigado pela preferencia.", estilos["Normal"]),
    ])
    documento.build(elementos)
    arquivo.seek(0)
    return arquivo
