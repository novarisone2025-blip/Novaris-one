import base64
import hashlib
import hmac
import os

from app.configuracao.configuracoes import configuracoes


def _chave() -> bytes:
    return hashlib.sha256(
        configuracoes.chave_criptografia_pagamentos.encode("utf-8")
    ).digest()


def _fluxo(chave: bytes, nonce: bytes, tamanho: int) -> bytes:
    blocos = []
    contador = 0
    while sum(len(bloco) for bloco in blocos) < tamanho:
        blocos.append(
            hmac.new(
                chave,
                nonce + contador.to_bytes(4, "big"),
                hashlib.sha256,
            ).digest()
        )
        contador += 1
    return b"".join(blocos)[:tamanho]


def criptografar_segredo(valor: str | None) -> bytes | None:
    if not valor:
        return None
    chave = _chave()
    nonce = os.urandom(16)
    dados = valor.encode("utf-8")
    cifra = bytes(
        original ^ mascara
        for original, mascara in zip(dados, _fluxo(chave, nonce, len(dados)))
    )
    assinatura = hmac.new(chave, nonce + cifra, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(nonce + assinatura + cifra)


def descriptografar_segredo(valor: bytes | None) -> str | None:
    if not valor:
        return None
    chave = _chave()
    pacote = base64.urlsafe_b64decode(valor)
    nonce, assinatura, cifra = pacote[:16], pacote[16:48], pacote[48:]
    assinatura_esperada = hmac.new(
        chave,
        nonce + cifra,
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(assinatura, assinatura_esperada):
        raise ValueError("Credencial de pagamento invalida.")
    dados = bytes(
        cifrado ^ mascara
        for cifrado, mascara in zip(cifra, _fluxo(chave, nonce, len(cifra)))
    )
    return dados.decode("utf-8")


def mascarar_segredo(valor: str | None) -> str | None:
    if not valor:
        return None
    if len(valor) <= 6:
        return "*" * len(valor)
    return f"{valor[:3]}{'*' * min(len(valor) - 6, 12)}{valor[-3:]}"
