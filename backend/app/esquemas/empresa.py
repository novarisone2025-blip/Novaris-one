from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EmpresaResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    cnpj: str | None
    telefone: str | None
    data_criacao: datetime
