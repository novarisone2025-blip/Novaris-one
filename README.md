# Novaris One

SaaS multiempresa para pequenos comerciantes e vendedores, com frontend React,
API FastAPI e persistência PostgreSQL. O sistema mantém os módulos existentes
de dashboard, estoque, vendas, caixas, financeiro, fornecedores, clientes,
compras, orçamentos, pagamentos PIX, relatórios, auditoria e backups.

## Situação da base

- PostgreSQL em produção e SQLite compatível com desenvolvimento local.
- Autenticação JWT com access token curto e refresh token rotativo.
- Refresh token em cookie `HttpOnly`, revogável no banco.
- Isolamento por `empresa_id` e auditoria por `usuario_id`.
- Docker com processos sem privilégio de root.
- Logs estruturados para stdout.
- Health check de API e banco.
- Frontend preparado para Vercel.
- Backend e PostgreSQL preparados para Render, Railway ou VPS.

## Estrutura

```text
backend/
  app/
    autenticacao/
    banco/
    configuracao/
    esquemas/
    modelos/
    rotas/
    servicos/
  scripts/
    inicializar_banco.py
    migrar_sqlite_postgresql.py
    validar_banco.py
frontend/
  src/
    componentes/
    contexts/
    paginas/
    servicos/
    styles/
deploy/
docs/
docker-compose.yml
docker-compose.production.yml
render.yaml
```

## Início rápido no Windows

O modo local antigo continua disponível:

1. Execute `INICIAR_NOVARIS.bat`.
2. Abra `http://127.0.0.1:5173`.
3. Para encerrar, execute `PARAR_NOVARIS.bat`.

Portas desse modo:

- Frontend: `5173`
- Backend: `8001`
- Swagger: `http://127.0.0.1:8001/docs`

Sem `DATABASE_URL`, o backend usa
`backend/novaris_one_etapa1.db` em SQLite.

## Executar com Docker

Requisitos: Docker Desktop com Docker Compose.

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

Endereços:

- Sistema: `http://localhost:3000`
- API: `http://localhost:8000`
- Documentação: `http://localhost:8000/docs`
- PostgreSQL: disponível apenas na rede interna do Compose

Verificação:

```powershell
docker compose ps
docker compose logs -f backend
```

Encerramento:

```powershell
docker compose down
```

O volume `postgres_data` preserva o banco. Não use `docker compose down -v`
em um ambiente com dados importantes.

## Backend separado

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:SECRET_KEY="gere-uma-chave-com-mais-de-32-caracteres"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Para PostgreSQL local:

```powershell
$env:DATABASE_URL="postgresql+psycopg://usuario:senha@localhost:5432/novaris"
python -m scripts.inicializar_banco
python -m scripts.validar_banco
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## Frontend separado

```powershell
cd frontend
corepack enable
pnpm install
$env:VITE_API_URL="http://127.0.0.1:8001"
pnpm run dev
```

Build:

```powershell
pnpm run build
```

## Variáveis de ambiente

As variáveis obrigatórias solicitadas estão em `.env.example`:

| Variável | Uso |
|---|---|
| `DATABASE_URL` | Conexão SQLAlchemy com SQLite ou PostgreSQL |
| `SECRET_KEY` | Assinatura dos tokens JWT |
| `JWT_EXPIRE_MINUTES` | Duração do access token |
| `FRONTEND_URL` | Origem principal do frontend |
| `APP_ENV` | `development`, `testing` ou `production` |
| `ALLOWED_ORIGINS` | Origens CORS separadas por vírgula |

Variáveis adicionais:

| Variável | Uso |
|---|---|
| `PAYMENT_ENCRYPTION_KEY` | Criptografia das credenciais de pagamento |
| `JWT_REFRESH_DAYS` | Duração máxima da sessão renovável |
| `PUBLIC_API_URL` | URL pública usada nos webhooks PIX |
| `ALLOWED_ORIGIN_REGEX` | Regra para subdomínios autorizados |
| `ALLOWED_HOSTS` | Hosts aceitos pela API |
| `COOKIE_DOMAIN` | Domínio compartilhado do cookie de refresh |
| `LOG_LEVEL` | `INFO`, `WARNING` ou `ERROR` |
| `ENABLE_DOCS` | Habilita Swagger e ReDoc |
| `WEB_CONCURRENCY` | Quantidade de workers Gunicorn |
| `VITE_API_URL` | URL da API embutida no build do frontend |

Em produção, a inicialização falha de propósito quando:

- `SECRET_KEY` ou `PAYMENT_ENCRYPTION_KEY` têm menos de 32 caracteres.
- `DATABASE_URL` aponta para SQLite.
- `FRONTEND_URL` não usa HTTPS.

## Autenticação

Rotas:

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

O access token é enviado no cabeçalho `Authorization: Bearer`. O refresh token
fica em cookie `HttpOnly`, é rotacionado a cada renovação e pode ser revogado
no logout. Alterar `SECRET_KEY` encerra todas as sessões existentes.

## Banco e migrations

Na inicialização:

1. O SQLAlchemy cria tabelas que ainda não existem.
2. `aplicar_migracoes_leves()` atualiza bancos antigos sem apagar registros.
3. `schema_migrations` registra as versões aplicadas.
4. O container executa `scripts.validar_banco` antes de iniciar a API.

Migração do SQLite existente para PostgreSQL:

```powershell
cd backend
$env:DATABASE_URL="postgresql+psycopg://usuario:senha@host:5432/novaris"
$env:SQLITE_SOURCE_URL="sqlite:///./novaris_one_etapa1.db"
python -m scripts.migrar_sqlite_postgresql
```

O destino deve estar vazio. O script não altera o SQLite, confere as chaves
estrangeiras, copia em ordem de dependência, ajusta sequências e compara as
contagens. Leia [MIGRACAO_POSTGRESQL.md](docs/MIGRACAO_POSTGRESQL.md).

## Logs e monitoramento

`GET /health` devolve:

```json
{
  "status_api": "ok",
  "status_banco": "ok",
  "versao": "1.1.0",
  "ambiente": "production",
  "data_hora_servidor": "2026-06-15T15:00:00+00:00"
}
```

A API registra login, renovação e logout, vendas, pagamentos, cancelamentos,
lançamentos financeiros, requisições HTTP e erros críticos. Senhas, tokens,
credenciais PIX, corpos e cabeçalhos de autenticação não são escritos nos logs.

## Testes

```powershell
cd backend
pytest -q
```

## Publicar somente o backend no Render

A pasta `backend` agora e autocontida e pode ser enviada para um repositorio
separado. Ela possui `Dockerfile`, `.env.example`, `render.yaml`, migrations e
instrucoes proprias em
[`backend/README_RENDER.md`](backend/README_RENDER.md).

O frontend deve compilar sem erros:

```powershell
cd frontend
pnpm run build
```

## Publicação

Arquitetura recomendada:

- Frontend: Vercel em `https://app.novarisagro.com.br`
- Backend: Render em `https://api.novarisagro.com.br`
- Banco: Render PostgreSQL
- Domínio principal: `novarisagro.com.br`

Passos completos:

- [DEPLOY_PRODUCAO.md](docs/DEPLOY_PRODUCAO.md)
- [MIGRACAO_POSTGRESQL.md](docs/MIGRACAO_POSTGRESQL.md)
- [OPERACAO_PRODUCAO.md](docs/OPERACAO_PRODUCAO.md)

## Cuidados

- Nunca envie `.env`, bancos `.db`, logs ou chaves ao Git.
- Não troque `PAYMENT_ENCRYPTION_KEY` sem recriptografar as credenciais PIX.
- Restrinja o acesso externo do PostgreSQL após uma migração.
- Ative backups gerenciados do provedor além do backup lógico do Novaris.
- Faça a primeira publicação em ambiente de teste antes de apontar o domínio.
