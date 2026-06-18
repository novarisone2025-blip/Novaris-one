# Migração SQLite para PostgreSQL

## Antes de começar

1. Encerre o Novaris para impedir novas gravações.
2. Faça uma cópia do arquivo SQLite.
3. Crie um banco PostgreSQL vazio.
4. Preserve a `PAYMENT_ENCRYPTION_KEY` usada no banco atual.

No Windows:

```powershell
Copy-Item backend\novaris_one_etapa1.db `
  backend\novaris_one_etapa1.antes-postgres.db
```

O arquivo original não é alterado pelo migrador.

## Configurar o ambiente

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
$env:DATABASE_URL="postgresql+psycopg://usuario:senha@host:5432/novaris"
$env:SQLITE_SOURCE_URL="sqlite:///./novaris_one_etapa1.db"
$env:SECRET_KEY="a-chave-jwt-do-novo-ambiente"
$env:PAYMENT_ENCRYPTION_KEY="a-mesma-chave-usada-nos-pagamentos-atuais"
```

Senhas com caracteres especiais precisam estar codificadas na URL. Quando o
provedor fornecer uma `DATABASE_URL` pronta, prefira usar essa URL.

## Executar

```powershell
python -m scripts.migrar_sqlite_postgresql
```

O script:

1. Confere `PRAGMA foreign_key_check` no SQLite.
2. Cria a estrutura atual no PostgreSQL.
3. Recusa um destino que já contenha dados.
4. Copia tabelas em ordem de dependência.
5. Preserva IDs e vínculos multiempresa.
6. Ajusta as sequências PostgreSQL.
7. Executa as migrations atuais.
8. Compara a quantidade de registros por tabela.

## Validar

```powershell
python -m scripts.validar_banco
```

Depois inicie a API e consulte:

```text
GET /health
```

Faça também uma conferência funcional:

- Login de um administrador.
- Quantidade de empresas e usuários.
- Produtos e saldo de estoque.
- Vendas, itens, cancelamentos e devoluções.
- Caixas abertos e fechados.
- Financeiro e relatórios.
- Fornecedores, clientes, compras e orçamentos.
- Configuração PIX mascarada.

## Migração para Render

Use temporariamente a URL externa do PostgreSQL para executar o migrador no seu
computador. Após concluir:

1. Confirme `/health`.
2. Faça login no sistema publicado.
3. Restrinja ou desabilite o acesso externo ao banco.
4. O backend do Render deve continuar usando a URL interna.

O Render recomenda a URL interna para serviços na mesma região, pois ela usa a
rede privada e reduz latência:
https://render.com/docs/postgresql-creating-connecting

## Retorno ao SQLite

Se a validação falhar, não apague o arquivo original. Interrompa o backend
PostgreSQL, restaure a configuração local sem `DATABASE_URL` e inicie novamente
com o SQLite copiado. Corrija a causa antes de tentar uma nova migração para um
banco PostgreSQL vazio.
