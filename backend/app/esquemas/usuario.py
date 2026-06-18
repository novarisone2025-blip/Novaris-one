from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.esquemas.autenticacao import _validar_senha_forte
from app.esquemas.empresa import EmpresaResposta


class UsuarioResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: EmailStr
    tipo_usuario: str
    cargo: str
    permissoes: list[str] = Field(default_factory=list)
    ativo: bool
    data_cadastro: datetime
    empresa: EmpresaResposta


class UsuarioInternoCriacao(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=72)
    cargo: Literal["Administrador", "Gerente", "Caixa", "Estoquista"]
    permissoes: list[str] = Field(default_factory=list)

    @field_validator("senha")
    @classmethod
    def validar_senha(cls, valor: str) -> str:
        return _validar_senha_forte(valor)


class UsuarioInternoAtualizacao(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    cargo: Literal["Administrador", "Gerente", "Caixa", "Estoquista"]
    permissoes: list[str] = Field(default_factory=list)
    ativo: bool = True
    nova_senha: str | None = Field(default=None, min_length=8, max_length=72)

    @field_validator("nova_senha")
    @classmethod
    def validar_nova_senha(cls, valor: str | None) -> str | None:
        return _validar_senha_forte(valor) if valor else None


class UsuarioInternoResposta(BaseModel):
    id: int
    nome: str
    email: EmailStr
    tipo_usuario: str
    cargo: str
    permissoes: list[str]
    ativo: bool
    data_cadastro: datetime


class CatalogoPermissoesResposta(BaseModel):
    permissoes: dict[str, str]
    predefinicoes_cargos: dict[str, list[str]]


class DesempenhoUsuarioResposta(BaseModel):
    usuario_id: int
    nome_usuario: str
    cargo_usuario: str
    ativo: bool
    quantidade_vendas: int
    total_vendido: Decimal
    total_descontos: Decimal
    formas_pagamento: dict[str, Decimal]
    primeira_venda: datetime | None
    ultima_venda: datetime | None
    movimentacoes_estoque: int
    entradas_estoque: int
    saidas_estoque: int
    unidades_entrada: int
    unidades_saida: int
    lancamentos_financeiros: int
    entradas_financeiras: Decimal
    saidas_financeiras: Decimal
