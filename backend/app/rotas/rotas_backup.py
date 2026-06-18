import io

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.autenticacao.seguranca import obter_usuario_logado
from app.banco.conexao import obter_sessao_banco
from app.esquemas.operacoes import BackupResposta, RestauracaoBackupResposta
from app.modelos.usuario import Usuario
from app.servicos.servico_backup import (
    buscar_backup,
    criar_backup,
    listar_backups,
    restaurar_backup,
)
from app.servicos.servico_permissoes import garantir_permissao


roteador_backup = APIRouter(prefix="/backups", tags=["Backup e seguranca"])


@roteador_backup.get("", response_model=list[BackupResposta])
def consultar_backups(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "backup_gerenciar")
    return listar_backups(usuario, sessao)


@roteador_backup.post(
    "",
    response_model=BackupResposta,
    status_code=status.HTTP_201_CREATED,
)
def gerar_backup_manual(
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "backup_gerenciar")
    return criar_backup(usuario, sessao)


@roteador_backup.get("/{backup_id}/download")
def baixar_backup(
    backup_id: int,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "backup_gerenciar")
    backup = buscar_backup(backup_id, usuario, sessao)
    return StreamingResponse(
        io.BytesIO(backup.conteudo),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{backup.nome_arquivo}"'
            )
        },
    )


@roteador_backup.post(
    "/{backup_id}/restaurar",
    response_model=RestauracaoBackupResposta,
)
def restaurar(
    backup_id: int,
    usuario: Usuario = Depends(obter_usuario_logado),
    sessao: Session = Depends(obter_sessao_banco),
):
    garantir_permissao(usuario, "backup_gerenciar")
    return restaurar_backup(backup_id, usuario, sessao)
