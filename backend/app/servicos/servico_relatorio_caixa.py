import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.servicos.servico_relatorios import formatar_moeda


def gerar_relatorio_fechamento(dados: dict, nome_empresa: str) -> io.BytesIO:
    arquivo = io.BytesIO()
    documento = SimpleDocTemplate(
        arquivo,
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    estilos = getSampleStyleSheet()
    linhas = [
        ["Valor inicial", formatar_moeda(dados["valor_inicial"])],
        ["Vendas em dinheiro", formatar_moeda(dados["total_dinheiro"])],
        [
            "Dinheiro recebido dos clientes",
            formatar_moeda(dados["total_recebido_dinheiro"]),
        ],
        [
            "Troco entregue",
            formatar_moeda(dados["total_troco_entregue"]),
        ],
        ["Vendas em PIX", formatar_moeda(dados["total_pix"])],
        ["Cartao de debito", formatar_moeda(dados["total_debito"])],
        ["Cartao de credito", formatar_moeda(dados["total_credito"])],
        ["Descontos", formatar_moeda(dados["total_descontos"])],
        ["Cancelamentos", formatar_moeda(dados["total_cancelamentos"])],
        ["Devolucoes", formatar_moeda(dados["total_devolucoes"])],
        ["Adicionais de troca", formatar_moeda(dados["total_adicionais_troca"])],
        ["Reforcos", formatar_moeda(dados["total_reforcos"])],
        ["Sangrias", formatar_moeda(dados["total_sangrias"])],
        ["Valor esperado em dinheiro", formatar_moeda(dados["valor_esperado"])],
        ["Valor contado", formatar_moeda(dados["valor_real"] or 0)],
        ["Diferenca", formatar_moeda(dados["diferenca"] or 0)],
    ]
    tabela = Table(linhas, colWidths=[95 * mm, 55 * mm])
    tabela.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9D7E3")),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BACKGROUND", (0, -3), (-1, -1), colors.HexColor("#F0EDFF")),
    ]))
    elementos = [
        Paragraph(f"<b>Fechamento de Caixa - {nome_empresa}</b>", estilos["Title"]),
        Paragraph(
            f"Caixa #{dados['id']} - {dados['nome_usuario']}",
            estilos["Heading2"],
        ),
        Paragraph(
            f"Abertura: {dados['data_abertura'].strftime('%d/%m/%Y %H:%M')} | "
            f"Fechamento: {dados['data_fechamento'].strftime('%d/%m/%Y %H:%M')}",
            estilos["Normal"],
        ),
        Spacer(1, 14),
        tabela,
        Spacer(1, 14),
        Paragraph(
            f"Vendas concluídas: <b>{dados['quantidade_vendas']}</b> | "
            f"Cancelamentos: <b>{dados['quantidade_cancelamentos']}</b> | "
            f"Situação: <b>{dados['situacao_diferenca'].title()}</b>",
            estilos["Normal"],
        ),
    ]
    documento.build(elementos)
    arquivo.seek(0)
    return arquivo
