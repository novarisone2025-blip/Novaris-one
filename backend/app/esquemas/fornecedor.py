from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class FornecedorBase(BaseModel):
    nome: str = Field(min_length=2, max_length=180)
    cnpj: str | None = Field(default=None, max_length=20)
    telefone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    contato: str | None = Field(default=None, max_length=120)


class FornecedorCriacao(FornecedorBase):
    pass


class FornecedorResposta(FornecedorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    data_criacao: datetime
    total_produtos: int = 0
