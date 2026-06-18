import argparse
import logging
import os
from pathlib import Path

from sqlalchemy import MetaData, create_engine, func, inspect, select, text

import app.modelos  # noqa: F401
from app.banco.conexao import BaseModelo, motor_banco
from app.banco.migracoes import aplicar_migracoes_leves
from app.configuracao.configuracoes import configuracoes
from app.configuracao.logs import configurar_logs


logger = logging.getLogger("novaris.migracao_dados")


def _argumentos() -> argparse.Namespace:
    analisador = argparse.ArgumentParser(
        description="Migra os dados do SQLite local para PostgreSQL.",
    )
    analisador.add_argument(
        "--origem",
        default=os.getenv(
            "SQLITE_SOURCE_URL",
            "sqlite:///./novaris_one_etapa1.db",
        ),
        help="URL SQLite de origem.",
    )
    return analisador.parse_args()


def _validar_origem(url: str) -> None:
    if not url.startswith("sqlite"):
        raise RuntimeError("--origem deve apontar para um banco SQLite.")
    if url.startswith("sqlite:///"):
        caminho = Path(url.removeprefix("sqlite:///")).resolve()
        if not caminho.exists():
            raise RuntimeError(f"Banco SQLite nao encontrado: {caminho}")


def _validar_destino() -> None:
    if motor_banco.dialect.name != "postgresql":
        raise RuntimeError(
            "DATABASE_URL deve apontar para o PostgreSQL de destino."
        )


def _validar_integridade_sqlite(motor_origem) -> None:
    with motor_origem.connect() as conexao:
        erros = conexao.execute(text("PRAGMA foreign_key_check")).all()
    if erros:
        amostra = ", ".join(str(item) for item in erros[:5])
        raise RuntimeError(
            "O SQLite possui chaves estrangeiras invalidas: " + amostra
        )


def _normalizar_linha(linha: dict) -> dict:
    return {
        chave: bytes(valor) if isinstance(valor, memoryview) else valor
        for chave, valor in linha.items()
    }


def _redefinir_sequencias(conexao) -> None:
    for tabela in BaseModelo.metadata.sorted_tables:
        if "id" not in tabela.c:
            continue
        conexao.execute(
            text(
                "SELECT setval("
                "pg_get_serial_sequence(:tabela, 'id'), "
                "COALESCE((SELECT MAX(id) FROM "
                f"{tabela.name}), 1), "
                f"(SELECT COUNT(*) > 0 FROM {tabela.name}))"
            ),
            {"tabela": tabela.name},
        )


def migrar(url_origem: str) -> None:
    _validar_origem(url_origem)
    _validar_destino()
    motor_origem = create_engine(
        url_origem,
        connect_args={"check_same_thread": False},
    )
    _validar_integridade_sqlite(motor_origem)

    BaseModelo.metadata.create_all(motor_banco)
    metadados_origem = MetaData()
    metadados_origem.reflect(bind=motor_origem)
    tabelas_origem = set(metadados_origem.tables)
    contagens_esperadas: dict[str, int] = {}

    with motor_banco.connect() as conexao:
        tabelas_com_dados = [
            tabela.name
            for tabela in BaseModelo.metadata.sorted_tables
            if conexao.scalar(
                select(func.count()).select_from(tabela)
            )
        ]
    if tabelas_com_dados:
        raise RuntimeError(
            "O PostgreSQL de destino nao esta vazio: "
            + ", ".join(tabelas_com_dados)
        )

    with motor_origem.connect() as origem, motor_banco.begin() as destino:
        for tabela_destino in BaseModelo.metadata.sorted_tables:
            nome = tabela_destino.name
            if nome not in tabelas_origem:
                logger.info("tabela nova ignorada na origem tabela=%s", nome)
                continue
            tabela_origem = metadados_origem.tables[nome]
            colunas_origem = set(tabela_origem.c.keys())
            obrigatorias_ausentes = [
                coluna.name
                for coluna in tabela_destino.c
                if coluna.name not in colunas_origem
                and not coluna.nullable
                and coluna.default is None
                and coluna.server_default is None
                and not coluna.primary_key
            ]
            if obrigatorias_ausentes:
                raise RuntimeError(
                    f"A tabela {nome} nao possui as colunas obrigatorias: "
                    + ", ".join(obrigatorias_ausentes)
                )
            colunas = [
                coluna.name
                for coluna in tabela_destino.c
                if coluna.name in colunas_origem
            ]
            linhas = origem.execute(
                select(*(tabela_origem.c[coluna] for coluna in colunas))
            ).mappings()
            lote = []
            quantidade = 0
            for linha in linhas:
                lote.append(_normalizar_linha(dict(linha)))
                if len(lote) == 500:
                    destino.execute(tabela_destino.insert(), lote)
                    quantidade += len(lote)
                    lote.clear()
            if lote:
                destino.execute(tabela_destino.insert(), lote)
                quantidade += len(lote)
            contagens_esperadas[nome] = quantidade
            logger.info("tabela migrada tabela=%s registros=%s", nome, quantidade)
        _redefinir_sequencias(destino)

    aplicar_migracoes_leves()
    with motor_banco.connect() as conexao:
        divergencias = []
        for nome, esperado in contagens_esperadas.items():
            tabela = BaseModelo.metadata.tables[nome]
            encontrado = conexao.scalar(
                select(func.count()).select_from(tabela)
            )
            if encontrado != esperado:
                divergencias.append(
                    f"{nome}: origem={esperado}, destino={encontrado}"
                )
    if divergencias:
        raise RuntimeError(
            "A validacao encontrou divergencias: " + "; ".join(divergencias)
        )
    logger.info(
        "migracao concluida tabelas=%s banco_destino=%s",
        len(contagens_esperadas),
        configuracoes.url_banco_dados.split("@")[-1],
    )


def main() -> None:
    configurar_logs()
    argumentos = _argumentos()
    migrar(argumentos.origem)


if __name__ == "__main__":
    main()
