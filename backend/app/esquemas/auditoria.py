from datetime import datetime

from pydantic import BaseModel


class LogAuditoriaResposta(BaseModel):
    id: int
    usuario_id: int
    nome_usuario: str
    cargo_usuario: str
    acao: str
    entidade: str
    entidade_id: int | None
    detalhes: str | None
    data_acao: datetime
