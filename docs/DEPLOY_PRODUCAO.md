# Publicação em produção

## Arquitetura recomendada

```text
app.novarisagro.com.br  -> Vercel / React
api.novarisagro.com.br  -> Render / FastAPI
PostgreSQL              -> Render, rede privada
```

Use os subdomínios personalizados antes do teste final de login. Assim o cookie
seguro de renovação pertence a `.novarisagro.com.br` e não depende de cookies
de terceiros entre `vercel.app` e `onrender.com`.

## 1. Preparar o repositório

1. Envie o projeto para um repositório privado no GitHub.
2. Confirme que `.env`, `*.db`, `*.log`, `.deps`, `node_modules` e `dist` não
   estão versionados.
3. Gere duas chaves diferentes com pelo menos 32 caracteres.

Exemplo em PowerShell:

```powershell
[Convert]::ToBase64String((1..48 | ForEach-Object {
  Get-Random -Maximum 256
}))
```

Uma chave será `SECRET_KEY`; a outra será `PAYMENT_ENCRYPTION_KEY`.

## 2. Backend e banco no Render

O arquivo `render.yaml` cria:

- Um PostgreSQL chamado `novaris-one-postgres`.
- Um web service Docker chamado `novaris-one-api`.
- Health check em `/health`.
- Segredos gerados pelo Render.

Passos:

1. Entre no Render e escolha `New > Blueprint`.
2. Conecte o repositório.
3. Selecione o `render.yaml` da raiz.
4. Revise os recursos e aplique o Blueprint.
5. Aguarde o PostgreSQL ficar disponível.
6. Aguarde o deploy do backend e confira os logs.
7. Abra `https://SEU-SERVICO.onrender.com/health`.

O Blueprint usa a conexão do banco criada pelo próprio Render. A documentação
oficial recomenda a URL interna para serviços na mesma região:
https://render.com/docs/postgresql-creating-connecting

### Domínio da API

No serviço do backend:

1. Abra `Settings > Custom Domains`.
2. Adicione `api.novarisagro.com.br`.
3. Crie no provedor DNS os registros exibidos pelo Render.
4. Volte ao Render e clique em `Verify`.

O Render cria e renova TLS automaticamente:
https://render.com/docs/custom-domains

Variáveis finais do backend:

```text
APP_ENV=production
DATABASE_URL=<fornecida pelo Render>
SECRET_KEY=<segredo forte>
PAYMENT_ENCRYPTION_KEY=<segredo forte e estável>
JWT_EXPIRE_MINUTES=30
JWT_REFRESH_DAYS=30
FRONTEND_URL=https://app.novarisagro.com.br
PUBLIC_API_URL=https://api.novarisagro.com.br
ALLOWED_ORIGINS=https://app.novarisagro.com.br,https://novarisagro.com.br
ALLOWED_HOSTS=api.novarisagro.com.br,*.onrender.com,localhost,127.0.0.1
COOKIE_DOMAIN=.novarisagro.com.br
ENABLE_DOCS=false
LOG_LEVEL=INFO
```

## 3. Frontend na Vercel

1. Na Vercel, escolha `Add New > Project`.
2. Importe o mesmo repositório.
3. Defina `Root Directory` como `frontend`.
4. Confirme o framework Vite.
5. Adicione a variável de produção:

```text
VITE_API_URL=https://api.novarisagro.com.br
```

6. Faça o deploy.
7. Em `Settings > Domains`, adicione `app.novarisagro.com.br`.
8. Configure no DNS os registros apresentados pela Vercel.

O arquivo `frontend/vercel.json` contém o rewrite necessário para a SPA. A
documentação oficial cobre Vite, variáveis e domínio:

- https://vercel.com/docs/frameworks/frontend/vite
- https://vercel.com/docs/environment-variables
- https://vercel.com/docs/domains/working-with-domains/add-a-domain

## 4. Domínio principal

Uma organização simples:

| Nome | Destino |
|---|---|
| `app` | registro informado pela Vercel |
| `api` | registro informado pelo Render |
| `@` | site institucional ou redirecionamento para `app` |
| `www` | site institucional ou redirecionamento |

Não copie valores de DNS de tutoriais antigos. Use os valores mostrados nos
painéis da Vercel e do Render no momento da configuração.

## 5. Migrar os dados atuais

Siga [MIGRACAO_POSTGRESQL.md](MIGRACAO_POSTGRESQL.md). Para Render, use a URL
externa somente durante a migração e mantenha o backend usando a URL interna.

## 6. PIX e webhook

Depois que `api.novarisagro.com.br` estiver ativo:

1. Defina `PUBLIC_API_URL=https://api.novarisagro.com.br`.
2. Entre no Novaris como administrador.
3. Abra `Configurações > Pagamentos`.
4. Salve novamente a configuração, se necessário.
5. Cadastre no provedor a URL de webhook exibida pelo sistema.
6. Faça uma venda PIX de valor baixo e valide a confirmação automática.

## Railway como alternativa

1. Crie um projeto no Railway.
2. Adicione PostgreSQL.
3. Adicione um serviço a partir do repositório.
4. Defina o diretório raiz do serviço como `backend`.
5. O Railway detectará `backend/Dockerfile`.
6. Referencie a `DATABASE_URL` do serviço PostgreSQL.
7. Cadastre as mesmas variáveis de produção do Render.
8. Em `Networking`, gere um domínio ou configure o domínio personalizado.

O Railway disponibiliza `DATABASE_URL` no serviço PostgreSQL e detecta um
`Dockerfile` na raiz do diretório-fonte:

- https://docs.railway.com/databases/postgresql
- https://docs.railway.com/builds/dockerfiles
- https://docs.railway.com/networking/public-networking

## VPS Linux

Recomendação mínima:

- Ubuntu LTS atualizado.
- 2 vCPU e 4 GB de RAM.
- Firewall com apenas SSH, HTTP e HTTPS.
- Docker instalado pelo repositório oficial.
- Backup externo do PostgreSQL.

Instalação oficial do Docker:
https://docs.docker.com/engine/install/ubuntu/

No servidor:

```bash
git clone URL_DO_REPOSITORIO novaris-one
cd novaris-one
cp .env.example .env
nano .env
docker compose -f docker-compose.production.yml up -d --build
docker compose -f docker-compose.production.yml logs -f backend
```

No `.env` da VPS, use:

```text
APP_ENV=production
POSTGRES_DB=novaris
POSTGRES_USER=novaris
POSTGRES_PASSWORD=<senha forte e codificada na DATABASE_URL>
DATABASE_URL=postgresql+psycopg://novaris:SENHA@banco:5432/novaris
SECRET_KEY=<segredo forte>
PAYMENT_ENCRYPTION_KEY=<segredo forte>
FRONTEND_URL=https://app.novarisagro.com.br
PUBLIC_API_URL=https://api.novarisagro.com.br
ALLOWED_ORIGINS=https://app.novarisagro.com.br
ALLOWED_HOSTS=api.novarisagro.com.br
COOKIE_DOMAIN=.novarisagro.com.br
```

O backend fica ligado apenas em `127.0.0.1:8000`. Use Caddy ou Nginx como proxy
HTTPS. Há um exemplo em `deploy/Caddyfile.example`.

## Checklist final

- `/health` retorna API e banco como `ok`.
- Cadastro, login, refresh e logout funcionam.
- Usuário de uma empresa não acessa dados de outra.
- Caixa, venda e baixa de estoque funcionam em conjunto.
- PIX manual e automático foram testados.
- PDF e Excel são gerados.
- Logs não mostram senhas, tokens ou credenciais.
- Backup do provedor está habilitado.
- Restauração foi ensaiada fora de produção.
- Domínios usam HTTPS.
- Swagger está desabilitado em produção ou protegido operacionalmente.
