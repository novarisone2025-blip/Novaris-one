import logging

from sqlalchemy import func, inspect, select, text

import app.modelos  # noqa: F401
from app.banco.conexao import BaseModelo, motor_banco
from app.configuracao.logs import configurar_logs


logger = logging.getLogger("novaris.validacao_banco")


def _assinatura_fk(chave: dict) -> tuple:
    return (
        tuple(chave.get("constrained_columns") or []),
        chave.get("referred_table"),
        tuple(chave.get("referred_columns") or []),
    )


def validar_estrutura_banco() -> dict:
    inspetor = inspect(motor_banco)
    tabelas_existentes = set(inspetor.get_table_names())
    validacao_estrita = motor_banco.dialect.name == "postgresql"
    erros: list[str] = []
    total_indices = 0
    total_fks = 0

    with motor_banco.connect() as conexao:
        conexao.execute(text("SELECT 1"))
        if motor_banco.dialect.name == "sqlite":
            violacoes = conexao.execute(
                text("PRAGMA foreign_key_check")
            ).all()
            if violacoes:
                erros.append(
                    f"SQLite possui {len(violacoes)} violacoes de FK"
                )
        for tabela in BaseModelo.metadata.sorted_tables:
            nome = tabela.name
            if nome not in tabelas_existentes:
                erros.append(f"tabela ausente: {nome}")
                continue

            colunas_existentes = {
                coluna["name"] for coluna in inspetor.get_columns(nome)
            }
            ausentes = set(tabela.c.keys()) - colunas_existentes
            if ausentes:
                erros.append(
                    f"colunas ausentes em {nome}: "
                    + ", ".join(sorted(ausentes))
                )

            fks_existentes = {
                _assinatura_fk(chave)
                for chave in inspetor.get_foreign_keys(nome)
            }
            fks_esperadas = {
                (
                    tuple(
                        elemento.parent.name
                        for elemento in restricao.elements
                    ),
                    restricao.referred_table.name,
                    tuple(
                        elemento.column.name
                        for elemento in restricao.elements
                    ),
                )
                for restricao in tabela.foreign_key_constraints
            }
            if validacao_estrita and fks_esperadas - fks_existentes:
                erros.append(f"chaves estrangeiras ausentes em {nome}")
            total_fks += len(fks_existentes)

            indices_existentes = {
                indice["name"] for indice in inspetor.get_indexes(nome)
            }
            indices_esperados = {
                indice.name for indice in tabela.indexes if indice.name
            }
            if validacao_estrita and indices_esperados - indices_existentes:
                erros.append(f"indices ausentes em {nome}")
            total_indices += len(indices_existentes)

            if "empresa_id" in tabela.c:
                nulos = conexao.scalar(
                    select(func.count())
                    .select_from(tabela)
                    .where(tabela.c.empresa_id.is_(None))
                )
                if nulos:
                    erros.append(f"{nome} possui {nulos} empresa_id nulos")

    if erros:
        raise RuntimeError("Banco invalido: " + "; ".join(erros))
    return {
        "dialeto": motor_banco.dialect.name,
        "tabelas": len(BaseModelo.metadata.tables),
        "chaves_estrangeiras": total_fks,
        "indices": total_indices,
    }


def main() -> None:
    configurar_logs()
    resumo = validar_estrutura_banco()
    logger.info(
        "banco validado dialeto=%s tabelas=%s fks=%s indices=%s",
        resumo["dialeto"],
        resumo["tabelas"],
        resumo["chaves_estrangeiras"],
        resumo["indices"],
    )


if __name__ == "__main__":
    main()
