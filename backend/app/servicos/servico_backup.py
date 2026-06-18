import gzip
import hashlib
import json
import base64
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modelos.empresa import Empresa
from app.modelos.auditoria import LogAuditoria
from app.modelos.caixa import Caixa
from app.modelos.cliente import Cliente
from app.modelos.comercial import (
    ItemOrcamento,
    ItemPedidoCompra,
    Orcamento,
    PedidoCompra,
)
from app.modelos.financeiro import LancamentoFinanceiro
from app.modelos.fornecedor import Fornecedor
from app.modelos.operacoes import (
    BackupEmpresa,
    DevolucaoVenda,
    ItemDevolucaoVenda,
    MovimentacaoCaixa,
)
from app.modelos.pagamento import (
    ConfiguracaoPagamento,
    EventoWebhookPagamento,
)
from app.modelos.produto import MovimentacaoEstoque, Produto
from app.modelos.usuario import Usuario
from app.modelos.venda import CancelamentoVenda, ItemVenda, Venda
from app.servicos.servico_auditoria import registrar_auditoria
from app.servicos.servico_criptografia import (
    criptografar_segredo,
    descriptografar_segredo,
)


MODELOS_BACKUP = [
    Usuario,
    Fornecedor,
    Produto,
    Caixa,
    Cliente,
    Venda,
    ItemVenda,
    Orcamento,
    ItemOrcamento,
    PedidoCompra,
    ItemPedidoCompra,
    CancelamentoVenda,
    DevolucaoVenda,
    ItemDevolucaoVenda,
    MovimentacaoEstoque,
    LancamentoFinanceiro,
    MovimentacaoCaixa,
    LogAuditoria,
    ConfiguracaoPagamento,
    EventoWebhookPagamento,
]

ORDEM_EXCLUSAO = [
    LogAuditoria,
    EventoWebhookPagamento,
    MovimentacaoEstoque,
    ItemOrcamento,
    Orcamento,
    ItemDevolucaoVenda,
    DevolucaoVenda,
    CancelamentoVenda,
    ItemVenda,
    Venda,
    LancamentoFinanceiro,
    ItemPedidoCompra,
    PedidoCompra,
    MovimentacaoCaixa,
    Caixa,
    Cliente,
    ConfiguracaoPagamento,
    Produto,
    Fornecedor,
]

ORDEM_RESTAURACAO = [
    Fornecedor,
    Produto,
    Cliente,
    Caixa,
    Venda,
    ItemVenda,
    Orcamento,
    ItemOrcamento,
    PedidoCompra,
    ItemPedidoCompra,
    CancelamentoVenda,
    DevolucaoVenda,
    ItemDevolucaoVenda,
    MovimentacaoEstoque,
    LancamentoFinanceiro,
    MovimentacaoCaixa,
    LogAuditoria,
    ConfiguracaoPagamento,
    EventoWebhookPagamento,
]


def _valor_json(valor):
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, bytes):
        return {"__bytes__": base64.b64encode(valor).decode("ascii")}
    return valor


def _linha(modelo, campos: list[str]) -> dict:
    return {
        campo: _valor_json(getattr(modelo, campo))
        for campo in campos
    }


def _registro_modelo(modelo) -> dict:
    return {
        coluna.name: _valor_json(getattr(modelo, coluna.name))
        for coluna in modelo.__table__.columns
    }


def _restaurar_valor(coluna, valor):
    if valor is None:
        return None
    if isinstance(valor, dict) and "__bytes__" in valor:
        return base64.b64decode(valor["__bytes__"])
    try:
        tipo = coluna.type.python_type
    except NotImplementedError:
        return valor
    if tipo is datetime and isinstance(valor, str):
        return datetime.fromisoformat(valor.replace("Z", "+00:00")).replace(
            tzinfo=None
        )
    if tipo is Decimal:
        return Decimal(valor)
    if tipo is bool:
        return bool(valor)
    if tipo is int:
        return int(valor)
    return valor


def _criar_conteudo_backup(
    usuario: Usuario,
    sessao: Session,
) -> bytes:
    empresa = sessao.get(Empresa, usuario.empresa_id)
    tabelas = {}
    for modelo in MODELOS_BACKUP:
        registros = sessao.scalars(
            select(modelo).where(modelo.empresa_id == usuario.empresa_id)
        ).all()
        tabelas[modelo.__tablename__] = [
            _registro_modelo(item) for item in registros
        ]
    dados = {
        "versao": 2,
        "empresa_id_origem": usuario.empresa_id,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "empresa": _linha(
            empresa,
            ["nome", "cnpj", "telefone", "data_criacao"],
        ),
        "tabelas": tabelas,
        "observacao": (
            "Snapshot logico completo e criptografado, isolado por empresa."
        ),
    }
    bruto = json.dumps(
        dados,
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    compactado = gzip.compress(bruto, compresslevel=9)
    texto = base64.b64encode(compactado).decode("ascii")
    return criptografar_segredo(texto)


def criar_backup(
    usuario: Usuario,
    sessao: Session,
    tipo: str = "manual",
) -> BackupEmpresa:
    conteudo = _criar_conteudo_backup(usuario, sessao)
    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    backup = BackupEmpresa(
        empresa_id=usuario.empresa_id,
        usuario_id=usuario.id,
        tipo=tipo,
        nome_arquivo=(
            f"novaris-empresa-{usuario.empresa_id}-"
            f"{agora.strftime('%Y%m%d-%H%M%S')}.novaris-backup"
        ),
        hash_sha256=hashlib.sha256(conteudo).hexdigest(),
        tamanho_bytes=len(conteudo),
        conteudo=conteudo,
    )
    sessao.add(backup)
    sessao.flush()
    registrar_auditoria(
        sessao,
        usuario,
        "backup_criado",
        "backup",
        backup.id,
        {"tipo": tipo, "tamanho_bytes": backup.tamanho_bytes},
    )
    sessao.commit()
    sessao.refresh(backup)
    return backup


def garantir_backup_automatico(
    usuario: Usuario,
    sessao: Session,
) -> None:
    hoje = datetime.now(timezone.utc).date()
    ultimo = sessao.scalar(
        select(BackupEmpresa)
        .where(
            BackupEmpresa.empresa_id == usuario.empresa_id,
            BackupEmpresa.tipo == "automatico",
        )
        .order_by(BackupEmpresa.data_criacao.desc())
        .limit(1)
    )
    if not ultimo or ultimo.data_criacao.date() < hoje:
        criar_backup(usuario, sessao, "automatico")


def listar_backups(
    usuario: Usuario,
    sessao: Session,
) -> list[BackupEmpresa]:
    garantir_backup_automatico(usuario, sessao)
    return list(sessao.scalars(
        select(BackupEmpresa)
        .where(BackupEmpresa.empresa_id == usuario.empresa_id)
        .order_by(BackupEmpresa.data_criacao.desc())
        .limit(50)
    ).all())


def buscar_backup(
    backup_id: int,
    usuario: Usuario,
    sessao: Session,
) -> BackupEmpresa:
    backup = sessao.scalar(
        select(BackupEmpresa).where(
            BackupEmpresa.id == backup_id,
            BackupEmpresa.empresa_id == usuario.empresa_id,
        )
    )
    if not backup:
        raise HTTPException(404, "Backup nao encontrado.")
    if hashlib.sha256(backup.conteudo).hexdigest() != backup.hash_sha256:
        raise HTTPException(409, "O arquivo de backup esta corrompido.")
    return backup


def restaurar_backup(
    backup_id: int,
    usuario: Usuario,
    sessao: Session,
) -> dict:
    backup = buscar_backup(backup_id, usuario, sessao)
    criar_backup(usuario, sessao, "pre_restauracao")
    try:
        texto = descriptografar_segredo(backup.conteudo)
        compactado = base64.b64decode(texto)
        dados = json.loads(gzip.decompress(compactado).decode("utf-8"))
    except (
        OSError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as erro:
        raise HTTPException(409, "Nao foi possivel ler o backup.") from erro
    if dados.get("empresa_id_origem") != usuario.empresa_id:
        raise HTTPException(
            403,
            "Este backup pertence a outra empresa.",
        )

    if dados.get("versao") != 2:
        raise HTTPException(
            409,
            "Este backup usa uma versao antiga e deve ser baixado para arquivo.",
        )

    empresa = sessao.get(Empresa, usuario.empresa_id)
    empresa.nome = dados["empresa"]["nome"]
    empresa.cnpj = dados["empresa"].get("cnpj")
    empresa.telefone = dados["empresa"].get("telefone")

    tabelas = dados["tabelas"]
    usuarios_atuais = {
        item.id: item
        for item in sessao.scalars(
            select(Usuario).where(Usuario.empresa_id == usuario.empresa_id)
        ).all()
    }
    usuarios_atualizados = 0
    colunas_usuario = {
        coluna.name: coluna for coluna in Usuario.__table__.columns
    }
    for item in tabelas.get("users", []):
        existente = usuarios_atuais.get(item["id"])
        if not existente:
            valores = {
                nome: _restaurar_valor(colunas_usuario[nome], valor)
                for nome, valor in item.items()
            }
            sessao.add(Usuario(**valores))
        else:
            for nome, valor in item.items():
                if nome not in {"id", "empresa_id"}:
                    setattr(
                        existente,
                        nome,
                        _restaurar_valor(colunas_usuario[nome], valor),
                    )
        usuarios_atualizados += 1
    sessao.flush()

    for modelo in ORDEM_EXCLUSAO:
        sessao.execute(
            delete(modelo).where(modelo.empresa_id == usuario.empresa_id)
        )
    sessao.flush()

    modelos_por_tabela = {
        modelo.__tablename__: modelo for modelo in ORDEM_RESTAURACAO
    }
    for tabela, modelo in modelos_por_tabela.items():
        colunas = {
            coluna.name: coluna for coluna in modelo.__table__.columns
        }
        for item in tabelas.get(tabela, []):
            valores = {
                nome: _restaurar_valor(colunas[nome], valor)
                for nome, valor in item.items()
            }
            if modelo is Venda:
                if valores.get("forma_pagamento") == "dinheiro":
                    if valores.get("valor_recebido") is None:
                        valores["valor_recebido"] = valores.get("valor_total")
                    if valores.get("troco_entregue") is None:
                        valores["troco_entregue"] = Decimal("0")
                else:
                    valores["valor_recebido"] = None
                    valores["troco_entregue"] = None
            if "empresa_id" in valores:
                valores["empresa_id"] = usuario.empresa_id
            sessao.add(modelo(**valores))
        sessao.flush()

    fornecedores_atualizados = len(tabelas.get("suppliers", []))
    produtos_atualizados = len(tabelas.get("products", []))

    registrar_auditoria(
        sessao,
        usuario,
        "backup_criado",
        "backup",
        backup.id,
        {
            "tipo": backup.tipo,
            "preservado_apos_restauracao": True,
        },
    )
    registrar_auditoria(
        sessao,
        usuario,
        "backup_restaurado",
        "backup",
        backup.id,
        {
            "produtos_atualizados": produtos_atualizados,
            "fornecedores_atualizados": fornecedores_atualizados,
            "usuarios_atualizados": usuarios_atualizados,
        },
    )
    sessao.commit()
    return {
        "backup_id": backup.id,
        "restaurado_em": datetime.now(timezone.utc).replace(tzinfo=None),
        "produtos_atualizados": produtos_atualizados,
        "fornecedores_atualizados": fornecedores_atualizados,
        "usuarios_atualizados": usuarios_atualizados,
    }
