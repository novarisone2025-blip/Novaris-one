# Operação em produção

## Health check

Monitore `GET /health` a cada 30 ou 60 segundos.

- HTTP `200`: API e banco disponíveis.
- HTTP `503`: API respondeu, mas o banco está indisponível.

Campos: `status_api`, `status_banco`, `versao`, `ambiente` e
`data_hora_servidor`.

## Logs

Os containers escrevem em stdout. Consulte:

```bash
docker compose logs -f backend
```

Eventos principais:

- `login concluido` e `login recusado`
- `sessao renovada` e `logout concluido`
- `venda registrada`
- `pagamento confirmado`
- `venda cancelada`
- `lancamento financeiro registrado`
- `erro_critico`

Cada requisição recebe `X-Request-ID`. Use esse identificador para relacionar
um erro informado pelo cliente ao log do servidor.

## Banco

O backend usa `pool_pre_ping`, reciclagem de conexões e pool configurável.

Estimativa de conexões por instância:

```text
WEB_CONCURRENCY * DB_POOL_SIZE
```

Com 2 workers e pool 5, uma instância pode manter cerca de 10 conexões, além do
`DB_MAX_OVERFLOW` durante picos. Ajuste conforme o limite do PostgreSQL.

Antes de cada release:

```bash
python -m scripts.inicializar_banco
python -m scripts.validar_banco
```

O entrypoint Docker já executa os dois comandos automaticamente.

## Backup

O Novaris mantém backup lógico por empresa e oferece backup manual. Isso não
substitui o backup gerenciado do PostgreSQL.

Política recomendada:

- Snapshot diário do provedor.
- Retenção mínima de 7 a 30 dias.
- Cópia externa semanal.
- Teste mensal de restauração em banco separado.

Não teste restauração diretamente no banco de produção.

## Segredos

- `SECRET_KEY`: pode ser rotacionada em incidente, mas derruba as sessões.
- `PAYMENT_ENCRYPTION_KEY`: não deve ser trocada sem recriptografar as
  credenciais de pagamento.
- `DATABASE_URL`: deve ficar apenas no gerenciador de segredos da plataforma.
- Tokens e segredos nunca devem ser enviados por e-mail ou commitados.

## Atualização

1. Gere backup.
2. Publique primeiro em ambiente de teste.
3. Execute testes e build.
4. Faça deploy do backend.
5. Confira `/health` e logs.
6. Faça deploy do frontend.
7. Teste login, PDV, estoque e financeiro.
8. Monitore erros após a publicação.

O backend é compatível com múltiplos workers porque os dados de sessão
renovável ficam no PostgreSQL. Não use SQLite com mais de uma instância.

## Incidentes

### Banco indisponível

1. Consulte `/health`.
2. Verifique o status do provedor.
3. Confira limite de conexões.
4. Não recrie o banco nem apague volumes.
5. Restaure somente a partir de um backup confirmado.

### Vazamento de JWT

1. Troque `SECRET_KEY`.
2. Reinicie o backend.
3. Todos os usuários precisarão entrar novamente.
4. Revise logs de auditoria.

### Credencial PIX exposta

1. Revogue o token no provedor.
2. Gere nova credencial.
3. Atualize no Novaris.
4. Não troque `PAYMENT_ENCRYPTION_KEY` como resposta automática ao incidente.

### Release com erro

1. Faça rollback da aplicação pela plataforma.
2. Não reverta o banco sem avaliar as migrations já aplicadas.
3. Use o `X-Request-ID` para localizar a falha.
