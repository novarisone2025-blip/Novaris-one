import logging
import sys

from app.configuracao.configuracoes import configuracoes


def configurar_logs() -> None:
    nivel = getattr(logging, configuracoes.nivel_log, logging.INFO)
    manipulador = logging.StreamHandler(sys.stdout)
    manipulador.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    raiz = logging.getLogger()
    raiz.handlers.clear()
    raiz.addHandler(manipulador)
    raiz.setLevel(nivel)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
