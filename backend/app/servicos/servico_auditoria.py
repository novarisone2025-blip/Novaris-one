import json

from sqlalchemy.orm import Session

from app.modelos.auditoria import LogAuditoria
from app.modelos.usuario import Usuario


def registrar_auditoria(
    sessao: Session,
    usuario: Usuario,
    acao: str,
    entidade: str,
    entidade_id: int | None = None,
    detalhes: dict | None = None,
) -> LogAuditoria:
    log = LogAuditoria(
        empresa_id=usuario.empresa_id,
        usuario_id=usuario.id,
        acao=acao,
        entidade=entidade,
        entidade_id=entidade_id,
        detalhes=(
            json.dumps(detalhes, ensure_ascii=True, default=str)
            if detalhes
            else None
        ),
    )
    sessao.add(log)
    return log
