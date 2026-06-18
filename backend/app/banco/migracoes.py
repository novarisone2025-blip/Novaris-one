import secrets

from sqlalchemy import inspect, text

from app.banco.conexao import motor_banco


def _adicionar_coluna(
    conexao,
    tabela: str,
    nome: str,
    definicao_sql: str,
    colunas_existentes: set[str],
):
    if nome not in colunas_existentes:
        conexao.execute(
            text(f"ALTER TABLE {tabela} ADD COLUMN {nome} {definicao_sql}")
        )


def _criar_indice(
    conexao,
    nome: str,
    tabela: str,
    colunas: str,
    unico: bool = False,
):
    tipo = "UNIQUE " if unico else ""
    conexao.execute(
        text(
            f"CREATE {tipo}INDEX IF NOT EXISTS {nome} "
            f"ON {tabela} ({colunas})"
        )
    )


def _contar(conexao, consulta: str) -> int:
    return int(conexao.scalar(text(consulta)) or 0)


def _validar_integridade_existente(conexao, tabelas: set[str]):
    verificacoes = {
        "usuarios sem empresa": (
            "SELECT COUNT(*) FROM users u "
            "LEFT JOIN companies c ON c.id = u.empresa_id "
            "WHERE c.id IS NULL"
        ),
        "fornecedores sem empresa": (
            "SELECT COUNT(*) FROM suppliers s "
            "LEFT JOIN companies c ON c.id = s.empresa_id "
            "WHERE c.id IS NULL"
        ),
        "produtos sem empresa": (
            "SELECT COUNT(*) FROM products p "
            "LEFT JOIN companies c ON c.id = p.empresa_id "
            "WHERE c.id IS NULL"
        ),
        "vendas sem usuario/empresa compativeis": (
            "SELECT COUNT(*) FROM sales s "
            "LEFT JOIN users u ON u.id = s.usuario_id "
            "WHERE u.id IS NULL OR u.empresa_id <> s.empresa_id"
        ),
        "vendas com caixa de outra empresa ou usuario": (
            "SELECT COUNT(*) FROM sales s "
            "LEFT JOIN cash_registers c ON c.id = s.caixa_id "
            "WHERE s.caixa_id IS NOT NULL AND (c.id IS NULL "
            "OR c.empresa_id <> s.empresa_id "
            "OR c.usuario_id <> s.usuario_id)"
        ),
        "itens sem venda/produto/empresa compativeis": (
            "SELECT COUNT(*) FROM sale_items i "
            "LEFT JOIN sales s ON s.id = i.venda_id "
            "LEFT JOIN products p ON p.id = i.produto_id "
            "WHERE s.id IS NULL OR p.id IS NULL "
            "OR i.empresa_id <> s.empresa_id "
            "OR i.empresa_id <> p.empresa_id"
        ),
        "movimentacoes sem produto/usuario/empresa compativeis": (
            "SELECT COUNT(*) FROM stock_movements m "
            "LEFT JOIN products p ON p.id = m.produto_id "
            "LEFT JOIN users u ON u.id = m.usuario_id "
            "WHERE p.id IS NULL OR u.id IS NULL "
            "OR m.empresa_id <> p.empresa_id "
            "OR m.empresa_id <> u.empresa_id"
        ),
        "movimentacoes com venda de outra empresa": (
            "SELECT COUNT(*) FROM stock_movements m "
            "LEFT JOIN sales s ON s.id = m.venda_id "
            "WHERE m.venda_id IS NOT NULL "
            "AND (s.id IS NULL OR s.empresa_id <> m.empresa_id)"
        ),
        "produtos com valores ou estoque invalidos": (
            "SELECT COUNT(*) FROM products WHERE quantidade < 0 "
            "OR estoque_minimo < 0 OR preco <= 0 OR preco_compra < 0"
        ),
        "vendas com totais invalidos": (
            "SELECT COUNT(*) FROM sales WHERE subtotal < 0 OR desconto < 0 "
            "OR valor_total < 0 "
            "OR ROUND(valor_total, 2) <> ROUND(subtotal - desconto, 2)"
        ),
        "vendas em dinheiro com recebimento invalido": (
            "SELECT COUNT(*) FROM sales WHERE "
            "(forma_pagamento = 'dinheiro' AND (valor_recebido IS NULL "
            "OR troco_entregue IS NULL OR valor_recebido < valor_total "
            "OR ROUND(troco_entregue, 2) "
            "<> ROUND(valor_recebido - valor_total, 2))) "
            "OR (forma_pagamento <> 'dinheiro' "
            "AND (valor_recebido IS NOT NULL OR troco_entregue IS NOT NULL))"
        ),
        "itens com quantidades ou totais invalidos": (
            "SELECT COUNT(*) FROM sale_items WHERE quantidade <= 0 "
            "OR valor_unitario < 0 OR custo_unitario < 0 "
            "OR ROUND(valor_total, 2) "
            "<> ROUND(valor_unitario * quantidade, 2) "
            "OR ROUND(custo_total, 2) "
            "<> ROUND(custo_unitario * quantidade, 2)"
        ),
    }
    if "financial_entries" in tabelas:
        verificacoes["lancamentos sem usuario/empresa compativeis"] = (
            "SELECT COUNT(*) FROM financial_entries f "
            "LEFT JOIN users u ON u.id = f.usuario_id "
            "WHERE u.id IS NULL OR u.empresa_id <> f.empresa_id"
        )
        verificacoes["lancamentos com valor ou tipo invalido"] = (
            "SELECT COUNT(*) FROM financial_entries WHERE valor <= 0 "
            "OR tipo NOT IN ('entrada', 'saida')"
        )
    if "sale_cancellations" in tabelas:
        verificacoes["cancelamentos sem venda/usuario compativeis"] = (
            "SELECT COUNT(*) FROM sale_cancellations c "
            "LEFT JOIN sales s ON s.id = c.venda_id "
            "LEFT JOIN users u ON u.id = c.usuario_id "
            "WHERE s.id IS NULL OR u.id IS NULL "
            "OR c.empresa_id <> s.empresa_id "
            "OR c.empresa_id <> u.empresa_id"
        )
        verificacoes["cancelamentos sem motivo"] = (
            "SELECT COUNT(*) FROM sale_cancellations "
            "WHERE motivo IS NULL OR TRIM(motivo) = ''"
        )
    if "payment_settings" in tabelas:
        verificacoes["pagamentos sem empresa"] = (
            "SELECT COUNT(*) FROM payment_settings p "
            "LEFT JOIN companies c ON c.id = p.empresa_id "
            "WHERE c.id IS NULL"
        )
        verificacoes["pagamentos com provedor invalido"] = (
            "SELECT COUNT(*) FROM payment_settings "
            "WHERE provedor NOT IN "
            "('manual', 'mercado_pago', 'asaas', 'efi')"
        )
    if "payment_webhook_events" in tabelas:
        verificacoes["webhooks sem empresa"] = (
            "SELECT COUNT(*) FROM payment_webhook_events w "
            "LEFT JOIN companies c ON c.id = w.empresa_id "
            "WHERE c.id IS NULL"
        )
        verificacoes["webhooks com venda de outra empresa"] = (
            "SELECT COUNT(*) FROM payment_webhook_events w "
            "LEFT JOIN sales s ON s.id = w.venda_id "
            "WHERE w.venda_id IS NOT NULL AND (s.id IS NULL "
            "OR s.empresa_id <> w.empresa_id)"
        )
    if "refresh_tokens" in tabelas:
        verificacoes["sessoes sem usuario/empresa compativeis"] = (
            "SELECT COUNT(*) FROM refresh_tokens r "
            "LEFT JOIN users u ON u.id = r.usuario_id "
            "LEFT JOIN companies c ON c.id = r.empresa_id "
            "WHERE u.id IS NULL OR c.id IS NULL "
            "OR u.empresa_id <> r.empresa_id"
        )

    erros = [
        f"{descricao}: {quantidade}"
        for descricao, consulta in verificacoes.items()
        if (quantidade := _contar(conexao, consulta))
    ]
    if erros:
        raise RuntimeError(
            "Integridade multiempresa invalida no banco: " + "; ".join(erros)
        )


def _criar_gatilhos_sqlite(conexao):
    gatilhos = {
        "trg_products_tenant_insert": (
            "BEFORE INSERT ON products WHEN NEW.fornecedor_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM suppliers s WHERE s.id = "
            "NEW.fornecedor_id AND s.empresa_id = NEW.empresa_id)"
        ),
        "trg_products_tenant_update": (
            "BEFORE UPDATE OF fornecedor_id, empresa_id ON products "
            "WHEN NEW.fornecedor_id IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM suppliers s WHERE s.id = NEW.fornecedor_id "
            "AND s.empresa_id = NEW.empresa_id)"
        ),
        "trg_sales_tenant_insert": (
            "BEFORE INSERT ON sales WHEN NOT EXISTS "
            "(SELECT 1 FROM users u WHERE u.id = NEW.usuario_id "
            "AND u.empresa_id = NEW.empresa_id)"
        ),
        "trg_sales_tenant_update": (
            "BEFORE UPDATE OF usuario_id, empresa_id ON sales WHEN NOT EXISTS "
            "(SELECT 1 FROM users u WHERE u.id = NEW.usuario_id "
            "AND u.empresa_id = NEW.empresa_id)"
        ),
        "trg_sales_cash_insert": (
            "BEFORE INSERT ON sales WHEN NEW.caixa_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM cash_registers c "
            "WHERE c.id = NEW.caixa_id AND c.empresa_id = NEW.empresa_id "
            "AND c.usuario_id = NEW.usuario_id)"
        ),
        "trg_sales_cash_update": (
            "BEFORE UPDATE OF caixa_id, usuario_id, empresa_id ON sales "
            "WHEN NEW.caixa_id IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM cash_registers c WHERE c.id = NEW.caixa_id "
            "AND c.empresa_id = NEW.empresa_id "
            "AND c.usuario_id = NEW.usuario_id)"
        ),
        "trg_sales_customer_insert": (
            "BEFORE INSERT ON sales WHEN NEW.cliente_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM customers c "
            "WHERE c.id = NEW.cliente_id AND c.empresa_id = NEW.empresa_id)"
        ),
        "trg_sales_customer_update": (
            "BEFORE UPDATE OF cliente_id, empresa_id ON sales "
            "WHEN NEW.cliente_id IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM customers c WHERE c.id = NEW.cliente_id "
            "AND c.empresa_id = NEW.empresa_id)"
        ),
        "trg_cash_registers_open_insert": (
            "BEFORE INSERT ON cash_registers WHEN NEW.status = 'aberto' "
            "AND EXISTS (SELECT 1 FROM cash_registers c "
            "WHERE c.empresa_id = NEW.empresa_id "
            "AND c.usuario_id = NEW.usuario_id AND c.status = 'aberto')"
        ),
        "trg_cash_registers_open_update": (
            "BEFORE UPDATE OF status, usuario_id, empresa_id "
            "ON cash_registers WHEN NEW.status = 'aberto' "
            "AND EXISTS (SELECT 1 FROM cash_registers c "
            "WHERE c.empresa_id = NEW.empresa_id "
            "AND c.usuario_id = NEW.usuario_id AND c.status = 'aberto' "
            "AND c.id <> NEW.id)"
        ),
        "trg_sale_items_tenant_insert": (
            "BEFORE INSERT ON sale_items WHEN NOT EXISTS "
            "(SELECT 1 FROM sales s WHERE s.id = NEW.venda_id "
            "AND s.empresa_id = NEW.empresa_id) OR NOT EXISTS "
            "(SELECT 1 FROM products p WHERE p.id = NEW.produto_id "
            "AND p.empresa_id = NEW.empresa_id)"
        ),
        "trg_sale_items_tenant_update": (
            "BEFORE UPDATE OF venda_id, produto_id, empresa_id ON sale_items "
            "WHEN NOT EXISTS (SELECT 1 FROM sales s WHERE s.id = NEW.venda_id "
            "AND s.empresa_id = NEW.empresa_id) OR NOT EXISTS "
            "(SELECT 1 FROM products p WHERE p.id = NEW.produto_id "
            "AND p.empresa_id = NEW.empresa_id)"
        ),
        "trg_movements_tenant_insert": (
            "BEFORE INSERT ON stock_movements WHEN NOT EXISTS "
            "(SELECT 1 FROM products p WHERE p.id = NEW.produto_id "
            "AND p.empresa_id = NEW.empresa_id) OR NOT EXISTS "
            "(SELECT 1 FROM users u WHERE u.id = NEW.usuario_id "
            "AND u.empresa_id = NEW.empresa_id) OR "
            "(NEW.venda_id IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM sales s WHERE s.id = NEW.venda_id "
            "AND s.empresa_id = NEW.empresa_id))"
        ),
        "trg_movements_tenant_update": (
            "BEFORE UPDATE OF produto_id, usuario_id, venda_id, empresa_id "
            "ON stock_movements WHEN NOT EXISTS "
            "(SELECT 1 FROM products p WHERE p.id = NEW.produto_id "
            "AND p.empresa_id = NEW.empresa_id) OR NOT EXISTS "
            "(SELECT 1 FROM users u WHERE u.id = NEW.usuario_id "
            "AND u.empresa_id = NEW.empresa_id) OR "
            "(NEW.venda_id IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM sales s WHERE s.id = NEW.venda_id "
            "AND s.empresa_id = NEW.empresa_id))"
        ),
        "trg_movements_purchase_insert": (
            "BEFORE INSERT ON stock_movements "
            "WHEN NEW.pedido_compra_id IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM purchase_orders p "
            "WHERE p.id = NEW.pedido_compra_id "
            "AND p.empresa_id = NEW.empresa_id)"
        ),
        "trg_movements_purchase_update": (
            "BEFORE UPDATE OF pedido_compra_id, empresa_id "
            "ON stock_movements WHEN NEW.pedido_compra_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM purchase_orders p "
            "WHERE p.id = NEW.pedido_compra_id "
            "AND p.empresa_id = NEW.empresa_id)"
        ),
        "trg_financial_tenant_insert": (
            "BEFORE INSERT ON financial_entries WHEN NOT EXISTS "
            "(SELECT 1 FROM users u WHERE u.id = NEW.usuario_id "
            "AND u.empresa_id = NEW.empresa_id)"
        ),
        "trg_financial_tenant_update": (
            "BEFORE UPDATE OF usuario_id, empresa_id ON financial_entries "
            "WHEN NOT EXISTS (SELECT 1 FROM users u WHERE u.id = "
            "NEW.usuario_id AND u.empresa_id = NEW.empresa_id)"
        ),
        "trg_financial_purchase_insert": (
            "BEFORE INSERT ON financial_entries "
            "WHEN NEW.pedido_compra_id IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM purchase_orders p "
            "WHERE p.id = NEW.pedido_compra_id "
            "AND p.empresa_id = NEW.empresa_id)"
        ),
        "trg_sale_cancellations_tenant_insert": (
            "BEFORE INSERT ON sale_cancellations WHEN NOT EXISTS "
            "(SELECT 1 FROM sales s WHERE s.id = NEW.venda_id "
            "AND s.empresa_id = NEW.empresa_id) OR NOT EXISTS "
            "(SELECT 1 FROM users u WHERE u.id = NEW.usuario_id "
            "AND u.empresa_id = NEW.empresa_id)"
        ),
        "trg_sale_cancellations_tenant_update": (
            "BEFORE UPDATE OF venda_id, usuario_id, empresa_id "
            "ON sale_cancellations WHEN NOT EXISTS "
            "(SELECT 1 FROM sales s WHERE s.id = NEW.venda_id "
            "AND s.empresa_id = NEW.empresa_id) OR NOT EXISTS "
            "(SELECT 1 FROM users u WHERE u.id = NEW.usuario_id "
            "AND u.empresa_id = NEW.empresa_id)"
        ),
    }
    for nome, definicao in gatilhos.items():
        conexao.execute(
            text(
                f"CREATE TRIGGER IF NOT EXISTS {nome} {definicao} "
                "BEGIN SELECT RAISE(ABORT, 'violacao de isolamento "
                "multiempresa'); END"
            )
        )


def _criar_constraints_postgresql(conexao):
    constraints = {
        "products": [
            (
                "fk_products_fornecedor_empresa",
                "FOREIGN KEY (fornecedor_id, empresa_id) "
                "REFERENCES suppliers(id, empresa_id) ON DELETE RESTRICT",
            ),
        ],
        "sales": [
            (
                "fk_sales_usuario_empresa",
                "FOREIGN KEY (usuario_id, empresa_id) "
                "REFERENCES users(id, empresa_id) ON DELETE RESTRICT",
            ),
            (
                "fk_sales_caixa_usuario_empresa",
                "FOREIGN KEY (caixa_id, empresa_id, usuario_id) "
                "REFERENCES cash_registers(id, empresa_id, usuario_id) "
                "ON DELETE RESTRICT",
            ),
            (
                "fk_sales_cliente_empresa",
                "FOREIGN KEY (cliente_id, empresa_id) "
                "REFERENCES customers(id, empresa_id) ON DELETE RESTRICT",
            ),
        ],
        "sale_items": [
            (
                "fk_sale_items_venda_empresa",
                "FOREIGN KEY (venda_id, empresa_id) "
                "REFERENCES sales(id, empresa_id) ON DELETE CASCADE",
            ),
            (
                "fk_sale_items_produto_empresa",
                "FOREIGN KEY (produto_id, empresa_id) "
                "REFERENCES products(id, empresa_id) ON DELETE RESTRICT",
            ),
        ],
        "stock_movements": [
            (
                "fk_stock_movements_produto_empresa",
                "FOREIGN KEY (produto_id, empresa_id) "
                "REFERENCES products(id, empresa_id) ON DELETE RESTRICT",
            ),
            (
                "fk_stock_movements_usuario_empresa",
                "FOREIGN KEY (usuario_id, empresa_id) "
                "REFERENCES users(id, empresa_id) ON DELETE RESTRICT",
            ),
            (
                "fk_stock_movements_venda_empresa",
                "FOREIGN KEY (venda_id, empresa_id) "
                "REFERENCES sales(id, empresa_id) ON DELETE RESTRICT",
            ),
            (
                "fk_stock_movements_pedido_empresa",
                "FOREIGN KEY (pedido_compra_id, empresa_id) "
                "REFERENCES purchase_orders(id, empresa_id) "
                "ON DELETE RESTRICT",
            ),
        ],
        "financial_entries": [
            (
                "fk_financial_entries_usuario_empresa",
                "FOREIGN KEY (usuario_id, empresa_id) "
                "REFERENCES users(id, empresa_id) ON DELETE RESTRICT",
            ),
            (
                "fk_financial_entries_pedido_empresa",
                "FOREIGN KEY (pedido_compra_id, empresa_id) "
                "REFERENCES purchase_orders(id, empresa_id) "
                "ON DELETE RESTRICT",
            ),
        ],
        "customers": [
            (
                "fk_customers_usuario_empresa",
                "FOREIGN KEY (usuario_id, empresa_id) "
                "REFERENCES users(id, empresa_id) ON DELETE RESTRICT",
            ),
        ],
        "audit_logs": [
            (
                "fk_audit_logs_usuario_empresa",
                "FOREIGN KEY (usuario_id, empresa_id) "
                "REFERENCES users(id, empresa_id) ON DELETE RESTRICT",
            ),
        ],
        "cash_registers": [
            (
                "fk_cash_registers_usuario_empresa",
                "FOREIGN KEY (usuario_id, empresa_id) "
                "REFERENCES users(id, empresa_id) ON DELETE RESTRICT",
            ),
        ],
        "sale_cancellations": [
            (
                "fk_sale_cancellations_venda_empresa",
                "FOREIGN KEY (venda_id, empresa_id) "
                "REFERENCES sales(id, empresa_id) ON DELETE RESTRICT",
            ),
            (
                "fk_sale_cancellations_usuario_empresa",
                "FOREIGN KEY (usuario_id, empresa_id) "
                "REFERENCES users(id, empresa_id) ON DELETE RESTRICT",
            ),
        ],
    }
    for tabela, itens in constraints.items():
        for nome, definicao in itens:
            conexao.execute(
                text(
                    "DO $$ BEGIN "
                    f"IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE "
                    f"conname = '{nome}') THEN ALTER TABLE {tabela} "
                    f"ADD CONSTRAINT {nome} {definicao}; END IF; END $$"
                )
            )
    checks = {
        "users": [
            (
                "ck_users_tipo_usuario",
                "tipo_usuario IN ('admin', 'comum')",
            ),
        ],
        "products": [
            ("ck_products_quantidade", "quantidade >= 0"),
            ("ck_products_estoque_minimo", "estoque_minimo >= 0"),
            ("ck_products_preco_venda", "preco > 0"),
            ("ck_products_preco_compra", "preco_compra >= 0"),
        ],
        "sales": [
            ("ck_sales_subtotal", "subtotal >= 0"),
            ("ck_sales_desconto", "desconto >= 0"),
            (
                "ck_sales_valor_total",
                "valor_total >= 0 AND valor_total = subtotal - desconto",
            ),
            (
                "ck_sales_forma_pagamento",
                "forma_pagamento IN "
                "('dinheiro', 'pix', 'debito', 'credito')",
            ),
            (
                "ck_sales_status",
                "status IN "
                "('aguardando_pagamento', 'pago', 'cancelado')",
            ),
            (
                "ck_sales_pagamento_dinheiro",
                "(forma_pagamento = 'dinheiro' "
                "AND valor_recebido IS NOT NULL "
                "AND troco_entregue IS NOT NULL "
                "AND valor_recebido >= valor_total "
                "AND troco_entregue = valor_recebido - valor_total) "
                "OR (forma_pagamento <> 'dinheiro' "
                "AND valor_recebido IS NULL "
                "AND troco_entregue IS NULL)",
            ),
        ],
        "sale_items": [
            ("ck_sale_items_quantidade", "quantidade > 0"),
            (
                "ck_sale_items_valores",
                "valor_unitario >= 0 "
                "AND valor_total = valor_unitario * quantidade",
            ),
            (
                "ck_sale_items_custos",
                "custo_unitario >= 0 "
                "AND custo_total = custo_unitario * quantidade",
            ),
        ],
        "stock_movements": [
            (
                "ck_stock_movements_tipo",
                "tipo IN ('entrada', 'saida')",
            ),
            ("ck_stock_movements_quantidade", "quantidade > 0"),
            (
                "ck_stock_movements_saldos",
                "quantidade_anterior >= 0 AND quantidade_atual >= 0",
            ),
        ],
        "financial_entries": [
            (
                "ck_financial_entries_tipo",
                "tipo IN ('entrada', 'saida')",
            ),
            ("ck_financial_entries_valor", "valor > 0"),
        ],
        "payment_settings": [
            (
                "ck_payment_settings_provedor",
                "provedor IN ('manual', 'mercado_pago', 'asaas', 'efi')",
            ),
        ],
        "cash_registers": [
            (
                "ck_cash_registers_status",
                "status IN ('aberto', 'fechado')",
            ),
            (
                "ck_cash_registers_valor_inicial",
                "valor_inicial >= 0",
            ),
        ],
    }
    for tabela, itens in checks.items():
        for nome, expressao in itens:
            conexao.execute(
                text(
                    "DO $$ BEGIN "
                    f"IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE "
                    f"conname = '{nome}') THEN ALTER TABLE {tabela} "
                    f"ADD CONSTRAINT {nome} CHECK ({expressao}); "
                    "END IF; END $$"
                )
            )


def aplicar_migracoes_leves():
    """Atualiza bancos existentes sem apagar os dados do comerciante."""
    inspetor = inspect(motor_banco)
    if "products" not in inspetor.get_table_names():
        return

    colunas_produtos = {
        coluna["name"] for coluna in inspetor.get_columns("products")
    }
    colunas_movimentos = {
        coluna["name"] for coluna in inspetor.get_columns("stock_movements")
    }

    with motor_banco.begin() as conexao:
        conexao.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "versao VARCHAR(100) PRIMARY KEY, "
                "aplicada_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        valor_booleano_verdadeiro = (
            "TRUE" if motor_banco.dialect.name == "postgresql" else "1"
        )
        colunas_usuarios = {
            coluna["name"] for coluna in inspetor.get_columns("users")
        }
        _adicionar_coluna(
            conexao,
            "users",
            "cargo",
            "VARCHAR(80) NOT NULL DEFAULT 'Usuario'",
            colunas_usuarios,
        )
        _adicionar_coluna(
            conexao,
            "users",
            "permissoes",
            "TEXT NOT NULL DEFAULT '[]'",
            colunas_usuarios,
        )
        conexao.execute(
            text(
                "UPDATE users SET cargo = 'Administrador', "
                "permissoes = '[\"dashboard_visualizar\","
                "\"vendas_operar\",\"vendas_relatorios\","
                "\"estoque_visualizar\",\"estoque_movimentar\","
                "\"estoque_gerenciar\",\"fornecedores_gerenciar\","
                "\"financeiro_visualizar\",\"financeiro_lancar\","
                "\"pagamentos_gerenciar\",\"relatorios_gerar\","
                "\"usuarios_gerenciar\",\"auditoria_visualizar\"]' "
                "WHERE tipo_usuario = 'admin'"
            )
        )
        _adicionar_coluna(
            conexao,
            "products",
            "categoria",
            "VARCHAR(100) NOT NULL DEFAULT 'Sem categoria'",
            colunas_produtos,
        )
        _adicionar_coluna(
            conexao,
            "products",
            "estoque_minimo",
            "INTEGER NOT NULL DEFAULT 0",
            colunas_produtos,
        )
        _adicionar_coluna(
            conexao,
            "products",
            "ativo",
            f"BOOLEAN NOT NULL DEFAULT {valor_booleano_verdadeiro}",
            colunas_produtos,
        )
        _adicionar_coluna(
            conexao,
            "products",
            "imagem_url",
            "VARCHAR(500)",
            colunas_produtos,
        )
        _adicionar_coluna(
            conexao,
            "products",
            "preco_compra",
            "NUMERIC(12, 2) NOT NULL DEFAULT 0",
            colunas_produtos,
        )
        _adicionar_coluna(
            conexao,
            "products",
            "fornecedor_id",
            "INTEGER",
            colunas_produtos,
        )

        novas_colunas_movimento = {
            "venda_id": "INTEGER",
            "quantidade_anterior": "INTEGER NOT NULL DEFAULT 0",
            "quantidade_atual": "INTEGER NOT NULL DEFAULT 0",
            "nome_produto": "VARCHAR(180) NOT NULL DEFAULT ''",
            "codigo_barras": "VARCHAR(80) NOT NULL DEFAULT ''",
            "nome_usuario": "VARCHAR(120) NOT NULL DEFAULT ''",
            "origem": "VARCHAR(30) NOT NULL DEFAULT 'estoque'",
        }
        for nome, definicao in novas_colunas_movimento.items():
            _adicionar_coluna(
                conexao,
                "stock_movements",
                nome,
                definicao,
                colunas_movimentos,
            )

        conexao.execute(
            text(
                "UPDATE stock_movements SET tipo = 'saida' "
                "WHERE tipo = 'venda'"
            )
        )

        tabelas = inspect(motor_banco).get_table_names()
        if "sales" in tabelas:
            colunas_vendas = {
                coluna["name"]
                for coluna in inspect(motor_banco).get_columns("sales")
            }
            _adicionar_coluna(
                conexao,
                "sales",
                "cliente_id",
                "INTEGER",
                colunas_vendas,
            )
            _adicionar_coluna(
                conexao,
                "sales",
                "caixa_id",
                "INTEGER",
                colunas_vendas,
            )
            _adicionar_coluna(
                conexao,
                "sales",
                "subtotal",
                "NUMERIC(12, 2) NOT NULL DEFAULT 0",
                colunas_vendas,
            )
            _adicionar_coluna(
                conexao,
                "sales",
                "status",
                "VARCHAR(30) NOT NULL DEFAULT 'pago'",
                colunas_vendas,
            )
            _adicionar_coluna(
                conexao,
                "sales",
                "codigo_pix",
                "VARCHAR(600)",
                colunas_vendas,
            )
            _adicionar_coluna(
                conexao,
                "sales",
                "provedor_pagamento",
                "VARCHAR(40)",
                colunas_vendas,
            )
            _adicionar_coluna(
                conexao,
                "sales",
                "referencia_pagamento",
                "VARCHAR(120)",
                colunas_vendas,
            )
            _adicionar_coluna(
                conexao,
                "sales",
                "data_pagamento",
                "TIMESTAMP",
                colunas_vendas,
            )
            _adicionar_coluna(
                conexao,
                "sales",
                "cobranca_externa_id",
                "VARCHAR(180)",
                colunas_vendas,
            )
            _adicionar_coluna(
                conexao,
                "sales",
                "status_cobranca",
                "VARCHAR(30)",
                colunas_vendas,
            )
            _adicionar_coluna(
                conexao,
                "sales",
                "desconto",
                "NUMERIC(12, 2) NOT NULL DEFAULT 0",
                colunas_vendas,
            )
            _adicionar_coluna(
                conexao,
                "sales",
                "forma_pagamento",
                "VARCHAR(30) NOT NULL DEFAULT 'dinheiro'",
                colunas_vendas,
            )
            _adicionar_coluna(
                conexao,
                "sales",
                "valor_recebido",
                "NUMERIC(12, 2)",
                colunas_vendas,
            )
            _adicionar_coluna(
                conexao,
                "sales",
                "troco_entregue",
                "NUMERIC(12, 2)",
                colunas_vendas,
            )
            conexao.execute(
                text(
                    "UPDATE sales SET subtotal = valor_total "
                    "WHERE subtotal = 0"
                )
            )
            conexao.execute(
                text(
                    "UPDATE sales SET valor_recebido = valor_total, "
                    "troco_entregue = 0 "
                    "WHERE forma_pagamento = 'dinheiro' "
                    "AND (valor_recebido IS NULL OR troco_entregue IS NULL)"
                )
            )
            conexao.execute(
                text(
                    "UPDATE sales SET valor_recebido = NULL, "
                    "troco_entregue = NULL "
                    "WHERE forma_pagamento <> 'dinheiro'"
                )
            )
        if "payment_settings" in tabelas:
            colunas_pagamentos = {
                coluna["name"]
                for coluna in inspect(motor_banco).get_columns(
                    "payment_settings"
                )
            }
            _adicionar_coluna(
                conexao,
                "payment_settings",
                "segredo_webhook_criptografado",
                "BLOB" if motor_banco.dialect.name == "sqlite" else "BYTEA",
                colunas_pagamentos,
            )
            _adicionar_coluna(
                conexao,
                "payment_settings",
                "token_webhook",
                "VARCHAR(80)",
                colunas_pagamentos,
            )
            configuracoes_sem_token = conexao.execute(
                text(
                    "SELECT id FROM payment_settings "
                    "WHERE token_webhook IS NULL OR token_webhook = ''"
                )
            ).all()
            for (configuracao_id,) in configuracoes_sem_token:
                conexao.execute(
                    text(
                        "UPDATE payment_settings SET token_webhook = :token "
                        "WHERE id = :configuracao_id"
                    ),
                    {
                        "token": secrets.token_urlsafe(32),
                        "configuracao_id": configuracao_id,
                    },
                )
        if "customers" in tabelas:
            colunas_clientes = {
                coluna["name"]
                for coluna in inspect(motor_banco).get_columns("customers")
            }
            _adicionar_coluna(
                conexao,
                "customers",
                "usuario_id",
                "INTEGER",
                colunas_clientes,
            )
            for nome, definicao in {
                "whatsapp": "VARCHAR(30)",
                "endereco": "VARCHAR(300)",
                "observacoes": "TEXT",
                "ativo": (
                    f"BOOLEAN NOT NULL DEFAULT {valor_booleano_verdadeiro}"
                ),
                "data_atualizacao": (
                    "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ),
            }.items():
                _adicionar_coluna(
                    conexao,
                    "customers",
                    nome,
                    definicao,
                    colunas_clientes,
                )
            conexao.execute(
                text(
                    "UPDATE customers SET usuario_id = ("
                    "SELECT MIN(u.id) FROM users u "
                    "WHERE u.empresa_id = customers.empresa_id"
                    ") WHERE usuario_id IS NULL"
                )
            )
        if "financial_entries" in tabelas:
            colunas_financeiro = {
                coluna["name"]
                for coluna in inspect(motor_banco).get_columns(
                    "financial_entries"
                )
            }
            _adicionar_coluna(
                conexao,
                "financial_entries",
                "pedido_compra_id",
                "INTEGER",
                colunas_financeiro,
            )
        _adicionar_coluna(
            conexao,
            "stock_movements",
            "pedido_compra_id",
            "INTEGER",
            colunas_movimentos,
        )
        if "sale_items" in tabelas:
            colunas_itens = {
                coluna["name"]
                for coluna in inspect(motor_banco).get_columns("sale_items")
            }
            _adicionar_coluna(
                conexao,
                "sale_items",
                "empresa_id",
                "INTEGER NOT NULL DEFAULT 0",
                colunas_itens,
            )
            _adicionar_coluna(
                conexao,
                "sale_items",
                "custo_unitario",
                "NUMERIC(12, 2) NOT NULL DEFAULT 0",
                colunas_itens,
            )
            conexao.execute(
                text(
                    "UPDATE sale_items SET empresa_id = COALESCE(("
                    "SELECT empresa_id FROM sales "
                    "WHERE sales.id = sale_items.venda_id"
                    "), empresa_id) WHERE empresa_id = 0"
                )
            )
            _adicionar_coluna(
                conexao,
                "sale_items",
                "custo_total",
                "NUMERIC(12, 2) NOT NULL DEFAULT 0",
                colunas_itens,
            )
        if "cash_registers" in tabelas:
            colunas_caixa = {
                coluna["name"]
                for coluna in inspect(motor_banco).get_columns("cash_registers")
            }
            for nome in (
                "total_sangrias",
                "total_reforcos",
                "total_devolucoes_dinheiro",
            ):
                _adicionar_coluna(
                    conexao,
                    "cash_registers",
                    nome,
                    "NUMERIC(12, 2) NOT NULL DEFAULT 0",
                    colunas_caixa,
                )
        conexao.execute(
            text(
                "UPDATE stock_movements SET "
                "nome_produto = COALESCE(("
                "SELECT nome FROM products "
                "WHERE products.id = stock_movements.produto_id"
                "), nome_produto), "
                "codigo_barras = COALESCE(("
                "SELECT codigo_barras FROM products "
                "WHERE products.id = stock_movements.produto_id"
                "), codigo_barras), "
                "nome_usuario = COALESCE(("
                "SELECT nome FROM users "
                "WHERE users.id = stock_movements.usuario_id"
                "), nome_usuario) "
                "WHERE nome_produto = '' OR nome_usuario = ''"
            )
        )

        conexao.execute(
            text(
                "UPDATE products SET fornecedor_id = NULL "
                "WHERE fornecedor_id IS NOT NULL AND NOT EXISTS ("
                "SELECT 1 FROM suppliers s WHERE s.id = products.fornecedor_id "
                "AND s.empresa_id = products.empresa_id)"
            )
        )

        indices = [
            ("uq_users_id_empresa", "users", "id, empresa_id", True),
            ("uq_suppliers_id_empresa", "suppliers", "id, empresa_id", True),
            ("uq_products_id_empresa", "products", "id, empresa_id", True),
            ("uq_sales_id_empresa", "sales", "id, empresa_id", True),
            ("uq_customers_id_empresa", "customers", "id, empresa_id", True),
            (
                "uq_financial_entries_id_empresa",
                "financial_entries",
                "id, empresa_id",
                True,
            ),
            (
                "ix_users_empresa_ativo",
                "users",
                "empresa_id, ativo",
                False,
            ),
            (
                "ix_users_empresa_cargo",
                "users",
                "empresa_id, cargo",
                False,
            ),
            (
                "ix_suppliers_empresa_nome",
                "suppliers",
                "empresa_id, nome",
                False,
            ),
            ("ix_products_empresa_nome", "products", "empresa_id, nome", False),
            (
                "ix_products_empresa_ativo_nome",
                "products",
                "empresa_id, ativo, nome",
                False,
            ),
            (
                "ix_products_empresa_estoque",
                "products",
                "empresa_id, ativo, quantidade, estoque_minimo",
                False,
            ),
            (
                "ix_products_empresa_categoria_nome",
                "products",
                "empresa_id, categoria, nome",
                False,
            ),
            (
                "ix_stock_movements_empresa_data",
                "stock_movements",
                "empresa_id, data_movimentacao",
                False,
            ),
            (
                "ix_stock_movements_empresa_tipo_data",
                "stock_movements",
                "empresa_id, tipo, data_movimentacao",
                False,
            ),
            (
                "ix_stock_movements_empresa_produto_data",
                "stock_movements",
                "empresa_id, produto_id, data_movimentacao",
                False,
            ),
            (
                "ix_stock_movements_venda_id",
                "stock_movements",
                "venda_id",
                False,
            ),
            (
                "ix_sales_empresa_data",
                "sales",
                "empresa_id, data_venda",
                False,
            ),
            (
                "ix_sales_caixa_id",
                "sales",
                "caixa_id",
                False,
            ),
            (
                "ix_sales_empresa_status_data",
                "sales",
                "empresa_id, status, data_venda",
                False,
            ),
            (
                "ix_sales_empresa_pagamento_data",
                "sales",
                "empresa_id, forma_pagamento, data_venda",
                False,
            ),
            (
                "ix_sales_empresa_cliente_data",
                "sales",
                "empresa_id, cliente_id, data_venda",
                False,
            ),
            (
                "uq_sales_empresa_cobranca_externa",
                "sales",
                "empresa_id, provedor_pagamento, cobranca_externa_id",
                True,
            ),
            (
                "ix_sale_items_empresa_venda",
                "sale_items",
                "empresa_id, venda_id",
                False,
            ),
            (
                "ix_sale_items_empresa_produto",
                "sale_items",
                "empresa_id, produto_id",
                False,
            ),
            (
                "uq_sale_items_id_empresa",
                "sale_items",
                "id, empresa_id",
                True,
            ),
        ]
        if "financial_entries" in tabelas:
            indices.extend([
                (
                    "ix_financial_entries_empresa_data",
                    "financial_entries",
                    "empresa_id, data_lancamento",
                    False,
                ),
                (
                    "ix_financial_entries_empresa_tipo_data",
                    "financial_entries",
                    "empresa_id, tipo, data_lancamento",
                    False,
                ),
            ])
        if "audit_logs" in tabelas:
            indices.extend([
                (
                    "ix_audit_logs_empresa_data",
                    "audit_logs",
                    "empresa_id, data_acao",
                    False,
                ),
                (
                    "ix_audit_logs_empresa_usuario_data",
                    "audit_logs",
                    "empresa_id, usuario_id, data_acao",
                    False,
                ),
            ])
        if "cash_registers" in tabelas:
            indices.extend([
                (
                    "uq_cash_registers_id_empresa",
                    "cash_registers",
                    "id, empresa_id",
                    True,
                ),
                (
                    "uq_cash_registers_id_empresa_usuario",
                    "cash_registers",
                    "id, empresa_id, usuario_id",
                    True,
                ),
                (
                    "ix_cash_registers_empresa_usuario_status",
                    "cash_registers",
                    "empresa_id, usuario_id, status",
                    False,
                ),
                (
                    "ix_cash_registers_empresa_abertura",
                    "cash_registers",
                    "empresa_id, data_abertura",
                    False,
                ),
            ])
        if "sale_cancellations" in tabelas:
            indices.extend([
                (
                    "uq_sale_cancellations_venda_empresa",
                    "sale_cancellations",
                    "venda_id, empresa_id",
                    True,
                ),
                (
                    "ix_sale_cancellations_empresa_data",
                    "sale_cancellations",
                    "empresa_id, data_cancelamento",
                    False,
                ),
                (
                    "ix_sale_cancellations_empresa_usuario_data",
                    "sale_cancellations",
                    "empresa_id, usuario_id, data_cancelamento",
                    False,
                ),
            ])
        if "sale_returns" in tabelas:
            indices.extend([
                (
                    "uq_sale_returns_id_empresa",
                    "sale_returns",
                    "id, empresa_id",
                    True,
                ),
                (
                    "ix_sale_returns_empresa_data",
                    "sale_returns",
                    "empresa_id, data_operacao",
                    False,
                ),
                (
                    "ix_sale_returns_empresa_venda",
                    "sale_returns",
                    "empresa_id, venda_id",
                    False,
                ),
            ])
        if "cash_movements" in tabelas:
            indices.extend([
                (
                    "ix_cash_movements_empresa_data",
                    "cash_movements",
                    "empresa_id, data_movimento",
                    False,
                ),
                (
                    "ix_cash_movements_empresa_caixa",
                    "cash_movements",
                    "empresa_id, caixa_id",
                    False,
                ),
            ])
        if "company_backups" in tabelas:
            indices.append((
                "ix_company_backups_empresa_data",
                "company_backups",
                "empresa_id, data_criacao",
                False,
            ))
        if "customers" in tabelas:
            indices.extend([
                (
                    "ix_customers_empresa_documento",
                    "customers",
                    "empresa_id, documento",
                    False,
                ),
                (
                    "ix_customers_empresa_telefone",
                    "customers",
                    "empresa_id, telefone",
                    False,
                ),
            ])
        if "purchase_orders" in tabelas:
            indices.extend([
                (
                    "ix_purchase_orders_empresa_status",
                    "purchase_orders",
                    "empresa_id, status",
                    False,
                ),
                (
                    "ix_purchase_orders_empresa_data",
                    "purchase_orders",
                    "empresa_id, data_criacao",
                    False,
                ),
            ])
        if "quotes" in tabelas:
            indices.extend([
                (
                    "ix_quotes_empresa_status_validade",
                    "quotes",
                    "empresa_id, status, validade",
                    False,
                ),
                (
                    "ix_quotes_empresa_cliente",
                    "quotes",
                    "empresa_id, cliente_id",
                    False,
                ),
            ])
        if "payment_settings" in tabelas:
            indices.append((
                "uq_payment_settings_token_webhook",
                "payment_settings",
                "token_webhook",
                True,
            ))
        if "payment_webhook_events" in tabelas:
            indices.extend([
                (
                    "uq_payment_webhook_evento_empresa",
                    "payment_webhook_events",
                    "empresa_id, provedor, evento_externo_id",
                    True,
                ),
                (
                    "ix_payment_webhook_empresa_data",
                    "payment_webhook_events",
                    "empresa_id, data_recebimento",
                    False,
                ),
                (
                    "ix_payment_webhook_cobranca",
                    "payment_webhook_events",
                    "empresa_id, provedor, cobranca_externa_id",
                    False,
                ),
            ])
        if "refresh_tokens" in tabelas:
            indices.extend([
                (
                    "ix_refresh_tokens_usuario_ativo",
                    "refresh_tokens",
                    "empresa_id, usuario_id, revogado",
                    False,
                ),
                (
                    "ix_refresh_tokens_expiracao",
                    "refresh_tokens",
                    "expiracao",
                    False,
                ),
            ])
        for nome, tabela, colunas, unico in indices:
            if tabela in tabelas:
                _criar_indice(
                    conexao,
                    nome,
                    tabela,
                    colunas,
                    unico,
                )

        tabelas_atuais = set(inspect(motor_banco).get_table_names())
        _validar_integridade_existente(conexao, tabelas_atuais)
        if motor_banco.dialect.name == "sqlite":
            _criar_gatilhos_sqlite(conexao)
        elif motor_banco.dialect.name == "postgresql":
            _criar_constraints_postgresql(conexao)
            conexao.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_cash_registers_usuario_aberto "
                    "ON cash_registers (empresa_id, usuario_id) "
                    "WHERE status = 'aberto'"
                )
            )
        conexao.execute(
            text(
                "INSERT INTO schema_migrations (versao) "
                "SELECT '20260609_integridade_multitenant_v1' "
                "WHERE NOT EXISTS (SELECT 1 FROM schema_migrations "
                "WHERE versao = '20260609_integridade_multitenant_v1')"
            )
        )
        conexao.execute(
            text(
                "INSERT INTO schema_migrations (versao) "
                "SELECT '20260615_producao_refresh_tokens_v1' "
                "WHERE NOT EXISTS (SELECT 1 FROM schema_migrations "
                "WHERE versao = "
                "'20260615_producao_refresh_tokens_v1')"
            )
        )
        conexao.execute(
            text(
                "INSERT INTO schema_migrations (versao) "
                "SELECT '20260610_operacoes_relatorios_backup_v1' "
                "WHERE NOT EXISTS (SELECT 1 FROM schema_migrations "
                "WHERE versao = "
                "'20260610_operacoes_relatorios_backup_v1')"
            )
        )
        conexao.execute(
            text(
                "INSERT INTO schema_migrations (versao) "
                "SELECT '20260610_fechamento_caixa_v1' "
                "WHERE NOT EXISTS (SELECT 1 FROM schema_migrations "
                "WHERE versao = '20260610_fechamento_caixa_v1')"
            )
        )
        conexao.execute(
            text(
                "INSERT INTO schema_migrations (versao) "
                "SELECT '20260610_usuarios_permissoes_auditoria_v1' "
                "WHERE NOT EXISTS (SELECT 1 FROM schema_migrations "
                "WHERE versao = "
                "'20260610_usuarios_permissoes_auditoria_v1')"
            )
        )
        conexao.execute(
            text(
                "INSERT INTO schema_migrations (versao) "
                "SELECT '20260610_cancelamento_vendas_v1' "
                "WHERE NOT EXISTS (SELECT 1 FROM schema_migrations "
                "WHERE versao = '20260610_cancelamento_vendas_v1')"
            )
        )
        conexao.execute(
            text(
                "INSERT INTO schema_migrations (versao) "
                "SELECT '20260612_compras_crm_orcamentos_v1' "
                "WHERE NOT EXISTS (SELECT 1 FROM schema_migrations "
                "WHERE versao = '20260612_compras_crm_orcamentos_v1')"
            )
        )
        conexao.execute(
            text(
                "INSERT INTO schema_migrations (versao) "
                "SELECT '20260613_pix_webhook_mercado_pago_v1' "
                "WHERE NOT EXISTS (SELECT 1 FROM schema_migrations "
                "WHERE versao = "
                "'20260613_pix_webhook_mercado_pago_v1')"
            )
        )
        conexao.execute(
            text(
                "INSERT INTO schema_migrations (versao) "
                "SELECT '20260613_pagamento_dinheiro_troco_v1' "
                "WHERE NOT EXISTS (SELECT 1 FROM schema_migrations "
                "WHERE versao = "
                "'20260613_pagamento_dinheiro_troco_v1')"
            )
        )
