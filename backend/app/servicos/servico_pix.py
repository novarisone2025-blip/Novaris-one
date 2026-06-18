import base64
import re
from decimal import Decimal

from reportlab.graphics import renderSVG
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing


def campo_pix(codigo: str, valor: str) -> str:
    return f"{codigo}{len(valor):02d}{valor}"


def crc16_pix(conteudo: str) -> str:
    resultado = 0xFFFF
    for caractere in conteudo.encode("utf-8"):
        resultado ^= caractere << 8
        for _ in range(8):
            resultado = (
                ((resultado << 1) ^ 0x1021) & 0xFFFF
                if resultado & 0x8000
                else (resultado << 1) & 0xFFFF
            )
    return f"{resultado:04X}"


def normalizar_texto_pix(valor: str, limite: int) -> str:
    texto = re.sub(r"[^A-Z0-9 ]", "", valor.upper())
    return texto[:limite] or "NOVARIS"


def gerar_codigo_pix(
    chave_pix: str,
    valor: Decimal,
    venda_id: int,
    nome_empresa: str,
) -> str:
    conta = (
        campo_pix("00", "BR.GOV.BCB.PIX")
        + campo_pix("01", chave_pix.strip())
        + campo_pix("02", f"Venda {venda_id}")
    )
    adicional = campo_pix("05", f"NOVARIS{venda_id}")
    conteudo = (
        campo_pix("00", "01")
        + campo_pix("26", conta)
        + campo_pix("52", "0000")
        + campo_pix("53", "986")
        + campo_pix("54", f"{valor:.2f}")
        + campo_pix("58", "BR")
        + campo_pix("59", normalizar_texto_pix(nome_empresa, 25))
        + campo_pix("60", "SAO PAULO")
        + campo_pix("62", adicional)
        + "6304"
    )
    return conteudo + crc16_pix(conteudo)


def gerar_qr_code_base64(conteudo: str) -> str:
    widget = QrCodeWidget(conteudo)
    largura, altura = widget.getBounds()[2:]
    desenho = Drawing(260, 260, transform=[260 / largura, 0, 0, 260 / altura, 0, 0])
    desenho.add(widget)
    svg = renderSVG.drawToString(desenho)
    return "data:image/svg+xml;base64," + base64.b64encode(
        svg.encode("utf-8")
    ).decode("ascii")
