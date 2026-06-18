import logging
import os
import re
import secrets
from pathlib import Path

from pydantic import BaseModel


PASTA_BACKEND = Path(__file__).resolve().parents[2]
PASTA_PROJETO = PASTA_BACKEND.parent


def _carregar_arquivo_env() -> None:
    """Carrega .env sem sobrescrever variaveis definidas pelo ambiente."""
    for caminho in (PASTA_PROJETO / ".env", PASTA_BACKEND / ".env"):
        if not caminho.exists():
            continue
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, valor = linha.split("=", 1)
            chave = chave.strip()
            valor = valor.strip().strip("'\"")
            if chave:
                os.environ.setdefault(chave, valor)


def _booleano(nome: str, padrao: bool) -> bool:
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


def _lista_variavel(nome: str, alternativa: str, padrao: str) -> list[str]:
    valor = os.getenv(nome) or os.getenv(alternativa) or padrao
    return [
        item.strip().rstrip("/")
        for item in valor.split(",")
        if item.strip()
    ]


def _normalizar_url_banco(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


def _chave_local_estavel() -> str:
    caminho = Path(
        os.getenv(
            "LOCAL_SECRET_FILE",
            str(PASTA_BACKEND / ".novaris-local-secret"),
        )
    )
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if caminho.exists():
        chave = caminho.read_text(encoding="utf-8").strip()
        if len(chave) >= 32:
            return chave
    chave = secrets.token_urlsafe(48)
    caminho.write_text(chave, encoding="utf-8")
    return chave


_carregar_arquivo_env()


class Configuracoes(BaseModel):
    nome_aplicacao: str = "Novaris One API"
    versao_aplicacao: str = os.getenv("APP_VERSION", "1.1.0")
    ambiente: str = (
        os.getenv("APP_ENV")
        or os.getenv("AMBIENTE")
        or "development"
    ).lower()
    url_banco_dados: str = _normalizar_url_banco(
        os.getenv(
            "DATABASE_URL",
            "sqlite:///./novaris_one_etapa1.db",
        )
    )
    chave_secreta: str = os.getenv("SECRET_KEY", "")
    chave_criptografia_pagamentos: str = os.getenv(
        "PAYMENT_ENCRYPTION_KEY",
        "",
    )
    url_frontend: str = os.getenv(
        "FRONTEND_URL",
        "http://localhost:5173",
    ).rstrip("/")
    url_publica_api: str = os.getenv("PUBLIC_API_URL", "").rstrip("/")
    algoritmo_jwt: str = "HS256"
    emissor_jwt: str = "novaris-one"
    audiencia_jwt: str = "novaris-one-web"
    minutos_token: int = int(
        os.getenv("JWT_EXPIRE_MINUTES")
        or os.getenv("ACCESS_TOKEN_MINUTES")
        or "30"
    )
    dias_refresh_token: int = int(os.getenv("JWT_REFRESH_DAYS", "30"))
    nome_cookie_refresh: str = os.getenv(
        "REFRESH_COOKIE_NAME",
        "novaris_refresh",
    )
    dominio_cookie: str | None = os.getenv("COOKIE_DOMAIN") or None
    origens_cors: list[str] = _lista_variavel(
        "ALLOWED_ORIGINS",
        "CORS_ORIGINS",
        (
            "http://localhost:5173,"
            "http://127.0.0.1:5173,"
            "http://localhost:3000,"
            "http://127.0.0.1:3000"
        ),
    )
    regex_origens_cors: str = os.getenv(
        "ALLOWED_ORIGIN_REGEX",
        r"^https://([a-z0-9-]+\.)?novarisagro\.com\.br$",
    )
    hosts_permitidos: list[str] = _lista_variavel(
        "ALLOWED_HOSTS",
        "TRUSTED_HOSTS",
        "localhost,127.0.0.1,testserver,*.novarisagro.com.br",
    )
    nivel_log: str = os.getenv("LOG_LEVEL", "INFO").upper()
    habilitar_documentacao: bool = _booleano(
        "ENABLE_DOCS",
        (
            os.getenv("APP_ENV")
            or os.getenv("AMBIENTE")
            or "development"
        ).lower() not in {"production", "producao", "prod"},
    )
    executar_migracoes_inicio: bool = _booleano(
        "RUN_MIGRATIONS_ON_STARTUP",
        True,
    )
    tamanho_pool_banco: int = int(os.getenv("DB_POOL_SIZE", "5"))
    excedente_pool_banco: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))

    @property
    def producao(self) -> bool:
        return self.ambiente in {"production", "producao", "prod"}

    @property
    def cookie_seguro(self) -> bool:
        return self.producao

    def validar(self) -> None:
        if not 5 <= self.minutos_token <= 1440:
            raise RuntimeError(
                "JWT_EXPIRE_MINUTES deve estar entre 5 e 1440 minutos."
            )
        if not 1 <= self.dias_refresh_token <= 180:
            raise RuntimeError(
                "JWT_REFRESH_DAYS deve estar entre 1 e 180 dias."
            )
        if self.producao:
            segredo_jwt_inseguro = self.chave_secreta.lower().startswith(
                ("gere-", "troque-", "defina-")
            )
            segredo_pagamento_inseguro = (
                self.chave_criptografia_pagamentos.lower().startswith(
                    ("gere-", "troque-", "defina-")
                )
            )
            if len(self.chave_secreta) < 32 or segredo_jwt_inseguro:
                raise RuntimeError(
                    "SECRET_KEY deve ser aleatoria e ter ao menos "
                    "32 caracteres em producao."
                )
            if (
                len(self.chave_criptografia_pagamentos) < 32
                or segredo_pagamento_inseguro
            ):
                raise RuntimeError(
                    "PAYMENT_ENCRYPTION_KEY deve ser aleatoria e ter ao "
                    "menos 32 caracteres em producao."
                )
            if self.url_banco_dados.startswith("sqlite"):
                raise RuntimeError(
                    "DATABASE_URL deve apontar para PostgreSQL em producao."
                )
            if not self.url_frontend.startswith("https://"):
                raise RuntimeError(
                    "FRONTEND_URL deve usar HTTPS em producao."
                )
        try:
            re.compile(self.regex_origens_cors)
        except re.error as erro:
            raise RuntimeError("ALLOWED_ORIGIN_REGEX invalida.") from erro


configuracoes = Configuracoes()
if (
    not configuracoes.producao
    and not os.getenv("ALLOWED_HOSTS")
    and not os.getenv("TRUSTED_HOSTS")
):
    configuracoes.hosts_permitidos = ["*"]
if not configuracoes.chave_secreta:
    if configuracoes.producao:
        configuracoes.validar()
    configuracoes.chave_secreta = _chave_local_estavel()
    logging.getLogger(__name__).warning(
        "SECRET_KEY ausente; usando chave local gerada para desenvolvimento."
    )
if not configuracoes.chave_criptografia_pagamentos:
    configuracoes.chave_criptografia_pagamentos = (
        configuracoes.chave_secreta
    )
if configuracoes.url_frontend not in configuracoes.origens_cors:
    configuracoes.origens_cors.append(configuracoes.url_frontend)
configuracoes.validar()
