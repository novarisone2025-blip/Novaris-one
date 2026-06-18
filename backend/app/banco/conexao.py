from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.configuracao.configuracoes import configuracoes


argumentos_motor = {
    "pool_pre_ping": True,
}
if configuracoes.url_banco_dados.startswith("sqlite"):
    argumentos_motor["connect_args"] = {"check_same_thread": False}
else:
    argumentos_motor.update(
        {
            "pool_size": configuracoes.tamanho_pool_banco,
            "max_overflow": configuracoes.excedente_pool_banco,
            "pool_recycle": 1800,
        }
    )

motor_banco = create_engine(
    configuracoes.url_banco_dados,
    **argumentos_motor,
)


if configuracoes.url_banco_dados.startswith("sqlite"):
    @event.listens_for(motor_banco, "connect")
    def ativar_chaves_estrangeiras_sqlite(conexao, _):
        cursor = conexao.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessaoBanco = sessionmaker(
    bind=motor_banco,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class BaseModelo(DeclarativeBase):
    pass


def obter_sessao_banco():
    """Abre uma sessao para a requisicao e fecha ao final."""
    sessao: Session = SessaoBanco()
    try:
        yield sessao
    finally:
        sessao.close()
