import logging
import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.banco.conexao import BaseModelo, motor_banco
from app.banco.migracoes import aplicar_migracoes_leves
from app.configuracao.logs import configurar_logs
import app.modelos  # noqa: F401


logger = logging.getLogger("novaris.migracoes")
CHAVE_TRAVA_POSTGRES = 718042651


def _inicializar_estrutura() -> None:
    if motor_banco.dialect.name != "postgresql":
        BaseModelo.metadata.create_all(motor_banco)
        aplicar_migracoes_leves()
        return

    with motor_banco.connect() as conexao_trava:
        conexao_trava.execute(
            text("SELECT pg_advisory_lock(:chave)"),
            {"chave": CHAVE_TRAVA_POSTGRES},
        )
        try:
            BaseModelo.metadata.create_all(motor_banco)
            aplicar_migracoes_leves()
        finally:
            conexao_trava.execute(
                text("SELECT pg_advisory_unlock(:chave)"),
                {"chave": CHAVE_TRAVA_POSTGRES},
            )


def inicializar_banco(tentativas: int = 12, intervalo: int = 5) -> None:
    ultimo_erro = None
    for tentativa in range(1, tentativas + 1):
        try:
            _inicializar_estrutura()
            return
        except OperationalError as erro:
            ultimo_erro = erro
            logger.warning(
                "banco_indisponivel tentativa=%s total=%s",
                tentativa,
                tentativas,
            )
            if tentativa < tentativas:
                time.sleep(intervalo)
    raise RuntimeError(
        "Nao foi possivel conectar ao banco para aplicar as migracoes."
    ) from ultimo_erro


def main() -> None:
    configurar_logs()
    logger.info("criacao_atualizacao_banco iniciada")
    inicializar_banco()
    logger.info("criacao_atualizacao_banco concluida")


if __name__ == "__main__":
    main()
