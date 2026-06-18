# Backend Novaris One no Render

Esta pasta e autocontida e pode ser publicada em um repositorio separado.
Ela contem a API FastAPI, modelos, servicos, migrations, Dockerfile e Blueprint
do Render.

## Publicacao automatica

1. Envie o conteudo desta pasta para a raiz de um repositorio privado.
2. No Render, escolha `New > Blueprint`.
3. Conecte o repositorio e selecione o arquivo `render.yaml`.
4. Confirme a criacao do PostgreSQL e do servico `novaris-one-api`.
5. Aguarde o pre-deploy aplicar e validar a estrutura do banco.
6. Confirme o endpoint `https://SEU-SERVICO.onrender.com/health`.

O plano definido e `starter` para a API e `basic-256mb` para o PostgreSQL.
Altere os planos no `render.yaml` antes da publicacao caso necessario.

## Variaveis importantes

O Blueprint configura automaticamente `DATABASE_URL`, `SECRET_KEY` e
`PAYMENT_ENCRYPTION_KEY`. Mantenha as duas chaves secretas estaveis depois do
primeiro deploy. Trocar `PAYMENT_ENCRYPTION_KEY` impede a leitura das
credenciais PIX ja armazenadas.

Antes de liberar o frontend, confirme:

```text
FRONTEND_URL=https://app.novarisagro.com.br
PUBLIC_API_URL=https://api.novarisagro.com.br
COOKIE_DOMAIN=.novarisagro.com.br
ALLOWED_ORIGINS=https://app.novarisagro.com.br,https://novarisagro.com.br
ALLOWED_HOSTS=api.novarisagro.com.br,*.onrender.com
```

## Publicacao manual no Render

Para criar apenas um Web Service, use:

```text
Runtime: Docker
Dockerfile: ./Dockerfile
Docker Context: .
Health Check Path: /health
```

Crie um PostgreSQL na mesma regiao e copie a URL interna para `DATABASE_URL`.
Cadastre as demais variaveis usando `.env.example` como referencia.

## Desenvolvimento e testes

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:DATABASE_URL="sqlite:///./novaris_one_etapa1.db"
python -m uvicorn app.main:app --reload --port 8000
pytest -q
```

O SQLite continua disponivel apenas para desenvolvimento. Em producao,
`APP_ENV=production` exige PostgreSQL e segredos fortes.
