import re

from pydantic import BaseModel, EmailStr, Field, field_validator


def _validar_senha_forte(senha: str) -> str:
    if not re.search(r"[A-Z]", senha):
        raise ValueError("A senha deve possuir uma letra maiuscula.")
    if not re.search(r"[a-z]", senha):
        raise ValueError("A senha deve possuir uma letra minuscula.")
    if not re.search(r"\d", senha):
        raise ValueError("A senha deve possuir um numero.")
    return senha


class DadosCadastro(BaseModel):
    nome_empresa: str = Field(min_length=2, max_length=150)
    cnpj: str | None = Field(default=None, max_length=20)
    telefone_empresa: str | None = Field(default=None, max_length=30)
    nome_usuario: str = Field(min_length=2, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=72)

    @field_validator("nome_empresa", "nome_usuario")
    @classmethod
    def limpar_nome(cls, valor: str) -> str:
        return " ".join(valor.split())

    @field_validator("cnpj", "telefone_empresa")
    @classmethod
    def limpar_opcional(cls, valor: str | None) -> str | None:
        return valor.strip() if valor and valor.strip() else None

    @field_validator("senha")
    @classmethod
    def validar_senha(cls, valor: str) -> str:
        return _validar_senha_forte(valor)


class DadosLogin(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1, max_length=72)


class RespostaToken(BaseModel):
    token_acesso: str
    tipo_token: str = "bearer"
    expira_em_segundos: int


class RespostaLogout(BaseModel):
    mensagem: str = "Sessao encerrada."
