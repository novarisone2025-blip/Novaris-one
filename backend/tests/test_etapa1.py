import hashlib
import hmac
import io
import os
from datetime import date, timedelta
from urllib.parse import urlsplit
from uuid import uuid4

os.environ["DATABASE_URL"] = "sqlite:///./teste_etapa1.db"
os.environ["SECRET_KEY"] = "chave-secreta-de-teste"

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.banco.conexao import BaseModelo, SessaoBanco, motor_banco
from app.banco.migracoes import aplicar_migracoes_leves
from app.configuracao.configuracoes import Configuracoes, _normalizar_url_banco
from app.main import app
from app.modelos.financeiro import LancamentoFinanceiro
from app.modelos.pagamento import EventoWebhookPagamento
from app.modelos.produto import MovimentacaoEstoque, Produto
from app.modelos.usuario import Usuario
from app.modelos.venda import CancelamentoVenda, ItemVenda, Venda
from scripts.validar_banco import validar_estrutura_banco


BaseModelo.metadata.create_all(motor_banco)
aplicar_migracoes_leves()
cliente = TestClient(app)


def abrir_caixa_teste(cabecalho, valor_inicial=100):
    resposta = cliente.post(
        "/caixa/abrir",
        headers=cabecalho,
        json={"valor_inicial": valor_inicial},
    )
    assert resposta.status_code == 200
    return resposta.json()


def test_pagamento_dinheiro_calcula_troco_e_integra_caixa_relatorios():
    identificador = uuid4().hex
    cadastro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Loja Troco",
            "nome_usuario": "Caixa do Troco",
            "email": f"troco-{identificador}@novaris.one",
            "senha": "SenhaForte123",
        },
    )
    cabecalho = {
        "Authorization": f"Bearer {cadastro.json()['token_acesso']}"
    }
    produto = cliente.post(
        "/estoque/produtos",
        headers=cabecalho,
        json={
            "codigo_barras": f"TROCO-{identificador}",
            "nome": "Produto com Troco",
            "quantidade": 5,
            "estoque_minimo": 1,
            "preco": 37.5,
            "preco_compra": 20,
        },
    ).json()
    caixa = abrir_caixa_teste(cabecalho, 100)

    pagamento_insuficiente = cliente.post(
        "/vendas",
        headers=cabecalho,
        json={
            "itens": [{
                "codigo_barras": produto["codigo_barras"],
                "quantidade": 1,
            }],
            "forma_pagamento": "dinheiro",
            "valor_recebido": 30,
        },
    )
    assert pagamento_insuficiente.status_code == 422
    assert "Faltam R$ 7.50" in pagamento_insuficiente.json()["detail"]
    estoque_antes = cliente.get(
        "/estoque/produtos",
        headers=cabecalho,
    ).json()
    assert next(
        item for item in estoque_antes if item["id"] == produto["id"]
    )["quantidade"] == 5

    venda = cliente.post(
        "/vendas",
        headers=cabecalho,
        json={
            "itens": [{
                "codigo_barras": produto["codigo_barras"],
                "quantidade": 1,
            }],
            "forma_pagamento": "dinheiro",
            "valor_recebido": 50,
        },
    )
    assert venda.status_code == 201
    dados_venda = venda.json()
    assert dados_venda["valor_total"] == "37.50"
    assert dados_venda["valor_recebido"] == "50.00"
    assert dados_venda["troco_entregue"] == "12.50"

    recentes = cliente.get("/vendas/recentes", headers=cabecalho).json()
    historico = next(
        item for item in recentes if item["id"] == dados_venda["id"]
    )
    assert historico["valor_recebido"] == "50.00"
    assert historico["troco_entregue"] == "12.50"
    assert historico["nome_usuario"] == "Caixa do Troco"
    assert historico["caixa_id"] == caixa["id"]
    assert historico["data_venda"]

    resumo_caixa = cliente.get("/caixa/atual", headers=cabecalho).json()
    assert resumo_caixa["total_dinheiro"] == "37.50"
    assert resumo_caixa["total_recebido_dinheiro"] == "50.00"
    assert resumo_caixa["total_troco_entregue"] == "12.50"
    assert resumo_caixa["valor_esperado"] == "137.50"

    fluxo = cliente.get(
        "/financeiro/fluxo-caixa",
        headers=cabecalho,
    ).json()
    movimento = next(
        item for item in fluxo
        if item["id"] == f"venda-{dados_venda['id']}"
    )
    assert movimento["valor"] == "37.50"
    assert movimento["forma_pagamento"] == "dinheiro"
    assert movimento["valor_recebido"] == "50.00"
    assert movimento["troco_entregue"] == "12.50"
    assert movimento["caixa_id"] == caixa["id"]

    comprovante = cliente.get(
        f"/vendas/{dados_venda['id']}/comprovante",
        headers=cabecalho,
    )
    assert comprovante.status_code == 200
    assert comprovante.content.startswith(b"%PDF")

    relatorio_excel = cliente.get(
        "/financeiro/relatorios/excel",
        headers=cabecalho,
    )
    pasta = load_workbook(io.BytesIO(relatorio_excel.content))
    cabecalhos = [
        celula.value for celula in pasta["Financeiro"][8]
    ]
    assert "Valor recebido" in cabecalhos
    assert "Troco entregue" in cabecalhos

    fechamento = cliente.post(
        "/caixa/fechar",
        headers=cabecalho,
        json={"valor_real": 137.5},
    )
    assert fechamento.status_code == 200
    assert fechamento.json()["diferenca"] == "0.00"
    relatorio_caixa = cliente.get(
        f"/caixa/{caixa['id']}/relatorio",
        headers=cabecalho,
    )
    assert relatorio_caixa.status_code == 200
    assert relatorio_caixa.content.startswith(b"%PDF")


def test_rota_dashboard_exige_login():
    resposta = cliente.get("/dashboard")
    assert resposta.status_code == 401


def test_refresh_token_logout_health_e_validacao_segura():
    identificador = uuid4().hex
    cadastro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Loja Sessao Segura",
            "nome_usuario": "Administrador Sessao",
            "email": f"sessao-{identificador}@novaris.one",
            "senha": "SenhaForte123",
        },
    )
    assert cadastro.status_code == 201
    token_inicial = cadastro.json()["token_acesso"]
    assert cadastro.json()["expira_em_segundos"] > 0
    assert cliente.cookies.get("novaris_refresh")

    renovacao = cliente.post("/auth/refresh")
    assert renovacao.status_code == 200
    assert renovacao.json()["token_acesso"] != token_inicial

    logout = cliente.post("/auth/logout")
    assert logout.status_code == 200
    assert cliente.post("/auth/refresh").status_code == 401

    health = cliente.get("/health")
    assert health.status_code == 200
    assert health.json()["status_api"] == "ok"
    assert health.json()["status_banco"] == "ok"
    assert health.json()["versao"]
    assert health.json()["data_hora_servidor"]

    senha_fraca = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Loja Invalida",
            "nome_usuario": "Usuario Invalido",
            "email": f"invalido-{identificador}@novaris.one",
            "senha": "senhafraca",
        },
    )
    assert senha_fraca.status_code == 422
    assert "senhafraca" not in senha_fraca.text


def test_estrutura_banco_possui_tabelas_indices_e_relacionamentos():
    resumo = validar_estrutura_banco()
    assert resumo["tabelas"] >= 20
    assert resumo["chaves_estrangeiras"] > 0
    assert resumo["indices"] > 0


def test_configuracao_producao_recusa_placeholder_e_normaliza_postgres():
    assert _normalizar_url_banco(
        "postgres://usuario:senha@host:5432/novaris"
    ).startswith("postgresql+psycopg://")
    configuracao = Configuracoes(
        ambiente="production",
        url_banco_dados=(
            "postgresql+psycopg://usuario:senha@host:5432/novaris"
        ),
        chave_secreta=(
            "gere-uma-chave-aleatoria-com-pelo-menos-32-caracteres"
        ),
        chave_criptografia_pagamentos=(
            "outra-chave-real-aleatoria-com-mais-de-32-caracteres"
        ),
        url_frontend="https://app.novarisagro.com.br",
    )
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        configuracao.validar()


def test_compras_clientes_orcamentos_e_isolamento_multiempresa():
    identificador = uuid4().hex
    cadastro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Loja Comercial Integrada",
            "nome_usuario": "Administrador Comercial",
            "email": f"comercial-{identificador}@novaris.one",
            "senha": "SenhaForte123",
        },
    )
    cabecalho = {
        "Authorization": f"Bearer {cadastro.json()['token_acesso']}"
    }
    fornecedor = cliente.post(
        "/fornecedores",
        headers=cabecalho,
        json={
            "nome": f"Distribuidor {identificador}",
            "telefone": "11999999999",
        },
    )
    assert fornecedor.status_code == 201
    fornecedor_id = fornecedor.json()["id"]
    produto = cliente.post(
        "/estoque/produtos",
        headers=cabecalho,
        json={
            "codigo_barras": f"COM-{identificador}",
            "nome": "Produto Comercial Integrado",
            "quantidade": 2,
            "estoque_minimo": 3,
            "preco": 25,
            "preco_compra": 10,
            "fornecedor_id": fornecedor_id,
        },
    )
    assert produto.status_code == 201
    produto = produto.json()

    sugestoes = cliente.get("/compras/sugestoes", headers=cabecalho)
    assert sugestoes.status_code == 200
    sugestao = next(
        item for item in sugestoes.json()
        if item["produto_id"] == produto["id"]
    )
    assert sugestao["quantidade_sugerida"] == 4
    assert sugestao["custo_estimado"] == "40.00"

    pedido = cliente.post(
        "/compras",
        headers=cabecalho,
        json={
            "fornecedor_id": fornecedor_id,
            "itens": [{
                "produto_id": produto["id"],
                "quantidade": sugestao["quantidade_sugerida"],
            }],
            "observacoes": "Reposicao automatica sugerida pelo sistema",
        },
    )
    assert pedido.status_code == 201
    pedido_id = pedido.json()["id"]
    assert pedido.json()["status"] == "pendente"
    assert cliente.patch(
        f"/compras/{pedido_id}/status",
        headers=cabecalho,
        json={"status": "enviado"},
    ).status_code == 200
    recebido = cliente.patch(
        f"/compras/{pedido_id}/status",
        headers=cabecalho,
        json={"status": "recebido"},
    )
    assert recebido.status_code == 200
    assert recebido.json()["nome_usuario_recebimento"] == (
        "Administrador Comercial"
    )
    produtos = cliente.get("/estoque/produtos", headers=cabecalho).json()
    assert next(
        item for item in produtos if item["id"] == produto["id"]
    )["quantidade"] == 6
    historico = cliente.get(
        "/estoque/movimentacoes",
        headers=cabecalho,
        params={"busca": produto["codigo_barras"]},
    ).json()
    assert any(
        item["origem"] == "pedido_compra"
        and item["quantidade"] == 4
        for item in historico
    )
    fluxo = cliente.get(
        "/financeiro/fluxo-caixa",
        headers=cabecalho,
    ).json()
    assert any(
        item["categoria"] == "Compras" and item["valor"] == "40.00"
        for item in fluxo
    )

    novo_cliente = cliente.post(
        "/clientes",
        headers=cabecalho,
        json={
            "nome": "Cliente Preferencial",
            "documento": f"CPF-{identificador[:20]}",
            "telefone": "11988887777",
            "whatsapp": "11988887777",
            "email": f"cliente-{identificador}@example.com",
            "endereco": "Rua Central, 100",
            "observacoes": "Prefere contato por WhatsApp",
        },
    )
    assert novo_cliente.status_code == 201
    cliente_id = novo_cliente.json()["id"]

    abrir_caixa_teste(cabecalho)
    venda = cliente.post(
        "/vendas",
        headers=cabecalho,
        json={
            "cliente_id": cliente_id,
            "itens": [{
                "codigo_barras": produto["codigo_barras"],
                "quantidade": 1,
            }],
            "forma_pagamento": "dinheiro",
        },
    )
    assert venda.status_code == 201
    assert venda.json()["cliente_id"] == cliente_id
    detalhe = cliente.get(
        f"/clientes/{cliente_id}",
        headers=cabecalho,
    )
    assert detalhe.status_code == 200
    assert detalhe.json()["total_gasto"] == "25.00"
    assert detalhe.json()["quantidade_compras"] == 1
    assert detalhe.json()["produtos_mais_comprados"][0]["quantidade"] == 1
    assert cliente.get(
        "/clientes/relatorios/pdf/arquivo",
        headers=cabecalho,
    ).content.startswith(b"%PDF")
    assert cliente.get(
        "/clientes/relatorios/excel/arquivo",
        headers=cabecalho,
    ).content.startswith(b"PK")

    orcamento = cliente.post(
        "/orcamentos",
        headers=cabecalho,
        json={
            "cliente_id": cliente_id,
            "itens": [{
                "produto_id": produto["id"],
                "quantidade": 2,
                "desconto": 5,
            }],
            "desconto": 3,
            "observacoes": "Entrega combinada com o cliente",
            "validade": str(date.today() + timedelta(days=7)),
        },
    )
    assert orcamento.status_code == 201
    orcamento_id = orcamento.json()["id"]
    assert orcamento.json()["valor_total"] == "42.00"
    assert orcamento.json()["nome_cliente"] == "Cliente Preferencial"
    assert orcamento.json()["cliente_documento"].startswith("CPF-")
    assert orcamento.json()["cliente_whatsapp"] == "11988887777"
    assert orcamento.json()["cliente_email"].startswith("cliente-")
    assert orcamento.json()["cliente_endereco"] == "Rua Central, 100"
    assert cliente.get(
        f"/orcamentos/{orcamento_id}/pdf",
        headers=cabecalho,
    ).content.startswith(b"%PDF")
    compartilhamento = cliente.get(
        f"/orcamentos/{orcamento_id}/compartilhar",
        headers=cabecalho,
    )
    assert compartilhamento.status_code == 200
    assert compartilhamento.json()["whatsapp_url"].startswith(
        "https://wa.me/"
    )
    produto_atualizado = cliente.put(
        f"/estoque/produtos/{produto['id']}",
        headers=cabecalho,
        json={
            "codigo_barras": produto["codigo_barras"],
            "nome": produto["nome"],
            "categoria": produto["categoria"],
            "preco": 40,
            "preco_compra": produto["preco_compra"],
            "fornecedor_id": fornecedor_id,
            "estoque_minimo": produto["estoque_minimo"],
            "imagem_url": produto["imagem_url"],
        },
    )
    assert produto_atualizado.status_code == 200
    conversao = cliente.post(
        f"/orcamentos/{orcamento_id}/converter",
        headers=cabecalho,
        json={"forma_pagamento": "dinheiro"},
    )
    assert conversao.status_code == 200
    assert conversao.json()["subtotal"] == "50.00"
    assert conversao.json()["desconto"] == "8.00"
    assert conversao.json()["valor_total"] == "42.00"
    produtos = cliente.get("/estoque/produtos", headers=cabecalho).json()
    assert next(
        item for item in produtos if item["id"] == produto["id"]
    )["quantidade"] == 3
    historico = cliente.get(
        "/estoque/movimentacoes",
        headers=cabecalho,
        params={"busca": produto["codigo_barras"]},
    ).json()
    assert any(
        item["origem"] == "venda" and item["quantidade"] == 2
        for item in historico
    )
    assert cliente.get(
        "/orcamentos",
        headers=cabecalho,
    ).json()[0]["status"] == "convertido"

    dashboard = cliente.get("/dashboard", headers=cabecalho).json()
    assert dashboard["total_clientes"] == 1
    assert dashboard["pedidos_compra_pendentes"] == 0
    assert dashboard["taxa_conversao_orcamentos"] == 100
    assert dashboard["clientes_mais_compram"][0]["nome"] == (
        "Cliente Preferencial"
    )

    outra_empresa = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Outra Empresa Comercial",
            "nome_usuario": "Outro Administrador",
            "email": f"outra-comercial-{identificador}@novaris.one",
            "senha": "SenhaForte123",
        },
    )
    cabecalho_outro = {
        "Authorization": (
            f"Bearer {outra_empresa.json()['token_acesso']}"
        )
    }
    assert cliente.get(
        f"/clientes/{cliente_id}",
        headers=cabecalho_outro,
    ).status_code == 404
    assert cliente.get(
        "/compras",
        headers=cabecalho_outro,
    ).json() == []
    assert cliente.get(
        "/orcamentos",
        headers=cabecalho_outro,
    ).json() == []


def test_cadastro_login_e_dashboard():
    email = f"teste-{uuid4().hex}@novaris.one"
    cadastro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Loja Teste",
            "cnpj": None,
            "telefone_empresa": "11999999999",
            "nome_usuario": "Usuário Teste",
            "email": email,
            "senha": "SenhaForte123",
        },
    )
    assert cadastro.status_code == 201
    token = cadastro.json()["token_acesso"]

    usuario = cliente.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert usuario.status_code == 200
    assert usuario.json()["empresa"]["nome"] == "Loja Teste"

    login = cliente.post(
        "/auth/login",
        json={"email": email, "senha": "SenhaForte123"},
    )
    assert login.status_code == 200

    dashboard = cliente.get(
        "/dashboard",
        headers={
            "Authorization": f"Bearer {login.json()['token_acesso']}"
        },
    )
    assert dashboard.status_code == 200
    assert dashboard.json()["total_clientes"] == 0


def test_fluxo_completo_do_estoque():
    email = f"estoque-{uuid4().hex}@novaris.one"
    cadastro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Mercado Teste",
            "cnpj": None,
            "telefone_empresa": None,
            "nome_usuario": "Comerciante Teste",
            "email": email,
            "senha": "SenhaForte123",
        },
    )
    token = cadastro.json()["token_acesso"]
    cabecalho = {"Authorization": f"Bearer {token}"}

    criacao = cliente.post(
        "/estoque/produtos",
        headers=cabecalho,
        json={
            "codigo_barras": "7891234567890",
            "nome": "Produto Teste",
            "quantidade": 10,
            "estoque_minimo": 5,
            "preco": 19.90,
        },
    )
    assert criacao.status_code == 201
    produto_id = criacao.json()["id"]

    listagem = cliente.get("/estoque/produtos", headers=cabecalho)
    assert listagem.status_code == 200
    assert len(listagem.json()) == 1

    entrada = cliente.post(
        f"/estoque/produtos/{produto_id}/movimentacoes",
        headers=cabecalho,
        json={"tipo": "entrada", "quantidade": 5},
    )
    assert entrada.json()["quantidade_atual"] == 15

    venda = cliente.post(
        f"/estoque/produtos/{produto_id}/movimentacoes",
        headers=cabecalho,
        json={"tipo": "venda", "quantidade": 3},
    )
    assert venda.json()["quantidade_atual"] == 12

    estoque_insuficiente = cliente.post(
        f"/estoque/produtos/{produto_id}/movimentacoes",
        headers=cabecalho,
        json={"tipo": "venda", "quantidade": 50},
    )
    assert estoque_insuficiente.status_code == 422

    edicao = cliente.put(
        f"/estoque/produtos/{produto_id}",
        headers=cabecalho,
        json={
            "codigo_barras": "7891234567890",
            "nome": "Produto Atualizado",
            "preco": 21.50,
            "estoque_minimo": 10,
        },
    )
    assert edicao.status_code == 200
    assert edicao.json()["nome"] == "Produto Atualizado"

    dashboard = cliente.get("/dashboard", headers=cabecalho)
    assert dashboard.json()["total_produtos"] == 1

    exclusao = cliente.delete(
        f"/estoque/produtos/{produto_id}",
        headers=cabecalho,
    )
    assert exclusao.status_code == 204

    listagem_final = cliente.get("/estoque/produtos", headers=cabecalho)
    assert listagem_final.json() == []


def test_historico_alertas_venda_e_relatorios():
    email = f"avancado-{uuid4().hex}@novaris.one"
    cadastro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Loja Avançada",
            "nome_usuario": "Responsável Estoque",
            "email": email,
            "senha": "SenhaForte123",
        },
    )
    token = cadastro.json()["token_acesso"]
    cabecalho = {"Authorization": f"Bearer {token}"}

    produto = cliente.post(
        "/estoque/produtos",
        headers=cabecalho,
        json={
            "codigo_barras": "789000000001",
            "nome": "Arroz Integral",
            "quantidade": 8,
            "estoque_minimo": 6,
            "preco": 12.50,
        },
    ).json()

    abrir_caixa_teste(cabecalho)
    venda = cliente.post(
        "/vendas",
        headers=cabecalho,
        json={"codigo_barras": "789000000001", "quantidade": 3},
    )
    assert venda.status_code == 201
    assert venda.json()["quantidade_atual"] == 5
    assert float(venda.json()["valor_total"]) == 37.5

    alertas = cliente.get("/estoque/alertas", headers=cabecalho)
    assert alertas.status_code == 200
    assert alertas.json()[0]["quantidade_faltante"] == 1

    historico = cliente.get(
        "/estoque/movimentacoes",
        headers=cabecalho,
        params={"busca": "Arroz", "tipo": "saida"},
    )
    assert historico.status_code == 200
    movimento = historico.json()[0]
    assert movimento["quantidade_anterior"] == 8
    assert movimento["quantidade_atual"] == 5
    assert movimento["nome_usuario"] == "Responsável Estoque"
    assert movimento["origem"] == "venda"

    dashboard = cliente.get("/dashboard", headers=cabecalho).json()
    assert dashboard["produtos_estoque_baixo"] == 1
    assert dashboard["unidades_para_repor"] == 1
    assert dashboard["total_vendas"] == 37.5

    pdf = cliente.get("/estoque/relatorios/pdf", headers=cabecalho)
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    excel = cliente.get("/estoque/relatorios/excel", headers=cabecalho)
    assert excel.status_code == 200
    assert excel.content.startswith(b"PK")


def test_venda_com_carrinho_desconto_pagamento_e_comprovante():
    email = f"carrinho-{uuid4().hex}@novaris.one"
    cadastro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Loja Carrinho",
            "nome_usuario": "Operador Caixa",
            "email": email,
            "senha": "SenhaForte123",
        },
    )
    cabecalho = {
        "Authorization": f"Bearer {cadastro.json()['token_acesso']}"
    }

    for codigo, nome, preco, quantidade in [
        ("10001", "Cafe", 20, 10),
        ("10002", "Leite", 8, 12),
    ]:
        resposta = cliente.post(
            "/estoque/produtos",
            headers=cabecalho,
            json={
                "codigo_barras": codigo,
                "nome": nome,
                "quantidade": quantidade,
                "estoque_minimo": 2,
                "preco": preco,
                "imagem_url": f"https://exemplo.com/{codigo}.jpg",
            },
        )
        assert resposta.status_code == 201

    busca = cliente.get("/vendas/produto/10001", headers=cabecalho)
    assert busca.status_code == 200
    assert busca.json()["nome"] == "Cafe"
    assert busca.json()["imagem_url"].endswith("10001.jpg")

    abrir_caixa_teste(cabecalho)
    venda = cliente.post(
        "/vendas",
        headers=cabecalho,
        json={
            "itens": [
                {"codigo_barras": "10001", "quantidade": 2},
                {"codigo_barras": "10002", "quantidade": 3},
            ],
            "desconto": 4,
            "forma_pagamento": "credito",
        },
    )
    assert venda.status_code == 201
    dados = venda.json()
    assert len(dados["itens"]) == 2
    assert float(dados["subtotal"]) == 64
    assert float(dados["desconto"]) == 4
    assert float(dados["valor_total"]) == 60
    assert dados["forma_pagamento"] == "credito"

    produtos = cliente.get("/estoque/produtos", headers=cabecalho).json()
    saldos = {produto["codigo_barras"]: produto["quantidade"] for produto in produtos}
    assert saldos == {"10001": 8, "10002": 9}

    financeiro = cliente.get("/vendas", headers=cabecalho)
    assert financeiro.status_code == 200
    assert financeiro.json()[0]["valor_total"] == "60.00"
    assert financeiro.json()[0]["quantidade_itens"] == 5

    comprovante = cliente.get(
        f"/vendas/{dados['id']}/comprovante",
        headers=cabecalho,
    )
    assert comprovante.status_code == 200
    assert comprovante.content.startswith(b"%PDF")


def test_fornecedores_dashboard_inteligente_e_financeiro():
    email = f"gestao-{uuid4().hex}@novaris.one"
    cadastro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Loja Gestao",
            "nome_usuario": "Gestor",
            "email": email,
            "senha": "SenhaForte123",
        },
    )
    cabecalho = {
        "Authorization": f"Bearer {cadastro.json()['token_acesso']}"
    }
    fornecedor = cliente.post(
        "/fornecedores",
        headers=cabecalho,
        json={
            "nome": "Distribuidora Teste",
            "telefone": "11999999999",
            "email": f"fornecedor-{uuid4().hex}@teste.com",
        },
    )
    assert fornecedor.status_code == 201

    produto = cliente.post(
        "/estoque/produtos",
        headers=cabecalho,
        json={
            "codigo_barras": f"produto-{uuid4().hex}",
            "nome": "Produto com Margem",
            "quantidade": 10,
            "estoque_minimo": 2,
            "preco": 30,
            "preco_compra": 18,
            "fornecedor_id": fornecedor.json()["id"],
        },
    )
    assert produto.status_code == 201

    abrir_caixa_teste(cabecalho)
    venda = cliente.post(
        "/vendas",
        headers=cabecalho,
        json={
            "itens": [{
                "codigo_barras": produto.json()["codigo_barras"],
                "quantidade": 2,
            }],
            "forma_pagamento": "debito",
        },
    )
    assert venda.status_code == 201

    despesa = cliente.post(
        "/financeiro/lancamentos",
        headers=cabecalho,
        json={
            "tipo": "saida",
            "categoria": "Operacional",
            "descricao": "Embalagens",
            "valor": 5,
        },
    )
    assert despesa.status_code == 201

    dashboard = cliente.get("/dashboard", headers=cabecalho).json()
    assert dashboard["faturamento_mensal"] == 60
    assert dashboard["lucro_mensal"] == 24
    assert dashboard["quantidade_vendas"] == 1
    assert dashboard["produtos_mais_vendidos"][0]["quantidade"] == 2

    resumo = cliente.get("/financeiro/resumo", headers=cabecalho).json()
    assert resumo["faturamento"] == "60.00"
    assert resumo["custo_produtos"] == "36.00"
    assert resumo["lucro_bruto"] == "24.00"
    assert resumo["saldo_caixa"] == "55.00"

    pdf = cliente.get(
        "/financeiro/relatorios/pdf",
        headers=cabecalho,
    )
    excel = cliente.get(
        "/financeiro/relatorios/excel",
        headers=cabecalho,
    )
    assert pdf.content.startswith(b"%PDF")
    assert excel.content.startswith(b"PK")


def test_pix_pendente_so_baixa_estoque_apos_confirmacao():
    email = f"pix-{uuid4().hex}@novaris.one"
    cadastro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Loja PIX",
            "nome_usuario": "Operador PIX",
            "email": email,
            "senha": "SenhaForte123",
        },
    )
    cabecalho = {
        "Authorization": f"Bearer {cadastro.json()['token_acesso']}"
    }
    configuracao = cliente.put(
        "/pagamentos/configuracao",
        headers=cabecalho,
        json={
            "provedor": "manual",
            "chave_pix": f"pix-{uuid4().hex}@teste.com",
            "token_api": "token-muito-secreto",
            "client_id": "cliente-teste",
            "client_secret": "segredo-cliente",
            "ativo": True,
        },
    )
    assert configuracao.status_code == 200
    assert configuracao.json()["possui_token_api"] is True
    assert "token-muito-secreto" not in configuracao.text

    produto = cliente.post(
        "/estoque/produtos",
        headers=cabecalho,
        json={
            "codigo_barras": f"pix-produto-{uuid4().hex}",
            "nome": "Produto PIX",
            "quantidade": 10,
            "estoque_minimo": 2,
            "preco": 25,
            "preco_compra": 10,
        },
    ).json()
    abrir_caixa_teste(cabecalho)
    venda = cliente.post(
        "/vendas",
        headers=cabecalho,
        json={
            "itens": [{
                "codigo_barras": produto["codigo_barras"],
                "quantidade": 2,
            }],
            "forma_pagamento": "pix",
        },
    )
    assert venda.status_code == 201
    dados_venda = venda.json()
    assert dados_venda["status"] == "aguardando_pagamento"
    assert dados_venda["codigo_pix"].startswith("000201")
    assert dados_venda["qr_code_pix"].startswith(
        "data:image/svg+xml;base64,"
    )

    produtos_antes = cliente.get(
        "/estoque/produtos",
        headers=cabecalho,
    ).json()
    assert produtos_antes[0]["quantidade"] == 10
    dashboard_antes = cliente.get("/dashboard", headers=cabecalho).json()
    assert dashboard_antes["faturamento_mensal"] == 0
    comprovante_antes = cliente.get(
        f"/vendas/{dados_venda['id']}/comprovante",
        headers=cabecalho,
    )
    assert comprovante_antes.status_code == 409

    confirmacao = cliente.post(
        f"/vendas/{dados_venda['id']}/confirmar-pagamento",
        headers=cabecalho,
    )
    assert confirmacao.status_code == 200
    assert confirmacao.json()["status"] == "pago"

    produtos_depois = cliente.get(
        "/estoque/produtos",
        headers=cabecalho,
    ).json()
    assert produtos_depois[0]["quantidade"] == 8
    dashboard_depois = cliente.get("/dashboard", headers=cabecalho).json()
    assert dashboard_depois["faturamento_mensal"] == 50
    comprovante = cliente.get(
        f"/vendas/{dados_venda['id']}/comprovante",
        headers=cabecalho,
    )
    assert comprovante.status_code == 200
    assert comprovante.content.startswith(b"%PDF")


def test_pix_mercado_pago_confirma_por_webhook_de_forma_idempotente(
    monkeypatch,
):
    import app.servicos.servico_vendas as servico_vendas
    import app.servicos.servico_webhook_pagamentos as servico_webhook
    from app.servicos.servico_gateway_pix import CobrancaPix

    identificador = uuid4().hex
    segredo_webhook = f"segredo-{identificador}"
    cobranca_id = f"mp-{identificador}"
    dados_cobranca = {}
    cadastro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Loja PIX Automatico",
            "nome_usuario": "Operador Webhook",
            "email": f"webhook-{identificador}@novaris.one",
            "senha": "SenhaForte123",
        },
    )
    cabecalho = {
        "Authorization": f"Bearer {cadastro.json()['token_acesso']}"
    }
    configuracao = cliente.put(
        "/pagamentos/configuracao",
        headers=cabecalho,
        json={
            "provedor": "mercado_pago",
            "chave_pix": f"{identificador}@pix",
            "token_api": f"APP_USR-{identificador}",
            "segredo_webhook": segredo_webhook,
            "ativo": True,
        },
    )
    assert configuracao.status_code == 200
    assert configuracao.json()["confirmacao_automatica"] is True
    assert configuracao.json()["possui_segredo_webhook"] is True
    url_webhook = configuracao.json()["webhook_url"]

    def criar_cobranca_falsa(config, venda, usuario, url_base):
        dados_cobranca["referencia"] = venda.referencia_pagamento
        return CobrancaPix(
            id_externo=cobranca_id,
            status="pending",
            codigo_pix="PIX-COPIA-E-COLA-TESTE",
            dados_provedor={},
        )

    monkeypatch.setattr(
        servico_vendas,
        "criar_cobranca_pix",
        criar_cobranca_falsa,
    )
    produto = cliente.post(
        "/estoque/produtos",
        headers=cabecalho,
        json={
            "codigo_barras": f"produto-webhook-{identificador}",
            "nome": "Produto confirmado por webhook",
            "quantidade": 10,
            "estoque_minimo": 2,
            "preco": 25,
            "preco_compra": 10,
        },
    ).json()
    abrir_caixa_teste(cabecalho)
    venda = cliente.post(
        "/vendas",
        headers=cabecalho,
        json={
            "itens": [{
                "codigo_barras": produto["codigo_barras"],
                "quantidade": 2,
            }],
            "forma_pagamento": "pix",
        },
    )
    assert venda.status_code == 201
    assert venda.json()["cobranca_externa_id"] == cobranca_id
    assert venda.json()["status"] == "aguardando_pagamento"

    monkeypatch.setattr(
        servico_webhook,
        "consultar_pagamento_mercado_pago",
        lambda config, pagamento_id: {
            "id": pagamento_id,
            "status": "approved",
            "external_reference": dados_cobranca["referencia"],
            "transaction_amount": 50,
        },
    )
    evento_id = f"evento-{identificador}"
    request_id = f"request-{identificador}"
    timestamp = "1710000000"
    manifesto = (
        f"id:{cobranca_id.lower()};"
        f"request-id:{request_id};"
        f"ts:{timestamp};"
    )
    assinatura = hmac.new(
        segredo_webhook.encode(),
        manifesto.encode(),
        hashlib.sha256,
    ).hexdigest()
    payload = {
        "id": evento_id,
        "type": "payment",
        "action": "payment.updated",
        "data": {"id": cobranca_id},
    }
    caminho_webhook = urlsplit(url_webhook).path
    parametros = {"data.id": cobranca_id, "type": "payment"}

    assinatura_invalida = cliente.post(
        caminho_webhook,
        params=parametros,
        headers={
            "x-request-id": request_id,
            "x-signature": f"ts={timestamp},v1=invalida",
        },
        json=payload,
    )
    assert assinatura_invalida.status_code == 401

    cabecalhos_webhook = {
        "x-request-id": request_id,
        "x-signature": f"ts={timestamp},v1={assinatura}",
    }
    confirmacao = cliente.post(
        caminho_webhook,
        params=parametros,
        headers=cabecalhos_webhook,
        json=payload,
    )
    assert confirmacao.status_code == 200
    assert confirmacao.json()["processado"] is True
    assert confirmacao.json()["status"] == "pago"

    repeticao = cliente.post(
        caminho_webhook,
        params=parametros,
        headers=cabecalhos_webhook,
        json=payload,
    )
    assert repeticao.status_code == 200
    assert repeticao.json()["processado"] is True

    status_pagamento = cliente.get(
        f"/vendas/{venda.json()['id']}/status-pagamento",
        headers=cabecalho,
    )
    assert status_pagamento.json()["status"] == "pago"
    produtos = cliente.get("/estoque/produtos", headers=cabecalho).json()
    produto_atual = next(
        item for item in produtos if item["id"] == produto["id"]
    )
    assert produto_atual["quantidade"] == 8
    dashboard = cliente.get("/dashboard", headers=cabecalho).json()
    assert dashboard["faturamento_mensal"] == 50

    with SessaoBanco() as sessao:
        eventos = sessao.scalars(
            select(EventoWebhookPagamento).where(
                EventoWebhookPagamento.evento_externo_id == evento_id
            )
        ).all()
        movimentos = sessao.scalars(
            select(MovimentacaoEstoque).where(
                MovimentacaoEstoque.venda_id == venda.json()["id"],
                MovimentacaoEstoque.origem == "venda",
            )
        ).all()
    assert len(eventos) == 1
    assert len(movimentos) == 1


def test_isolamento_multiempresa_na_api_e_no_banco():
    identificador = uuid4().hex
    email_a = f"empresa-a-{identificador}@novaris.one"
    email_b = f"empresa-b-{identificador}@novaris.one"

    cadastro_a = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Empresa Isolada A",
            "nome_usuario": "Administrador A",
            "email": email_a,
            "senha": "SenhaForte123",
        },
    )
    cadastro_b = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Empresa Isolada B",
            "nome_usuario": "Administrador B",
            "email": email_b,
            "senha": "SenhaForte123",
        },
    )
    assert cadastro_a.status_code == 201
    assert cadastro_b.status_code == 201
    cabecalho_a = {
        "Authorization": f"Bearer {cadastro_a.json()['token_acesso']}"
    }
    cabecalho_b = {
        "Authorization": f"Bearer {cadastro_b.json()['token_acesso']}"
    }

    fornecedor_a = cliente.post(
        "/fornecedores",
        headers=cabecalho_a,
        json={"nome": f"Fornecedor A {identificador}"},
    ).json()
    produto_a = cliente.post(
        "/estoque/produtos",
        headers=cabecalho_a,
        json={
            "codigo_barras": f"A-{identificador}",
            "nome": "Produto exclusivo A",
            "quantidade": 10,
            "estoque_minimo": 2,
            "preco": 20,
            "preco_compra": 8,
            "fornecedor_id": fornecedor_a["id"],
        },
    ).json()
    produto_b = cliente.post(
        "/estoque/produtos",
        headers=cabecalho_b,
        json={
            "codigo_barras": f"B-{identificador}",
            "nome": "Produto exclusivo B",
            "quantidade": 10,
            "estoque_minimo": 2,
            "preco": 30,
            "preco_compra": 12,
        },
    ).json()
    abrir_caixa_teste(cabecalho_a)
    venda_a = cliente.post(
        "/vendas",
        headers=cabecalho_a,
        json={
            "itens": [{
                "codigo_barras": produto_a["codigo_barras"],
                "quantidade": 1,
            }],
            "forma_pagamento": "dinheiro",
        },
    ).json()
    cliente.put(
        "/pagamentos/configuracao",
        headers=cabecalho_a,
        json={
            "provedor": "manual",
            "chave_pix": f"{identificador}@pix",
            "ativo": True,
        },
    )

    produtos_b = cliente.get(
        "/estoque/produtos",
        headers=cabecalho_b,
    ).json()
    assert {produto["id"] for produto in produtos_b} == {produto_b["id"]}
    assert cliente.post(
        f"/estoque/produtos/{produto_a['id']}/movimentacoes",
        headers=cabecalho_b,
        json={"tipo": "entrada", "quantidade": 1},
    ).status_code == 404
    assert cliente.post(
        "/estoque/produtos",
        headers=cabecalho_b,
        json={
            "codigo_barras": f"INV-{identificador}",
            "nome": "Produto com fornecedor externo",
            "quantidade": 1,
            "estoque_minimo": 0,
            "preco": 10,
            "fornecedor_id": fornecedor_a["id"],
        },
    ).status_code == 404
    assert cliente.get(
        f"/vendas/{venda_a['id']}/comprovante",
        headers=cabecalho_b,
    ).status_code == 404
    assert cliente.get(
        "/pagamentos/configuracao",
        headers=cabecalho_b,
    ).json()["configurado"] is False
    assert cliente.get(
        "/estoque/movimentacoes",
        headers=cabecalho_b,
    ).json()[0]["codigo_barras"] == produto_b["codigo_barras"]

    with SessaoBanco() as sessao:
        usuario_a = sessao.scalar(
            select(Usuario).where(Usuario.email == email_a)
        )
        usuario_b = sessao.scalar(
            select(Usuario).where(Usuario.email == email_b)
        )
        produto_modelo_b = sessao.scalar(
            select(Produto).where(Produto.id == produto_b["id"])
        )

        with pytest.raises(IntegrityError):
            sessao.add(
                LancamentoFinanceiro(
                    empresa_id=usuario_a.empresa_id,
                    usuario_id=usuario_b.id,
                    tipo="saida",
                    categoria="Teste",
                    descricao="Vinculo entre empresas",
                    valor=1,
                )
            )
            sessao.commit()
        sessao.rollback()

        with pytest.raises(IntegrityError):
            sessao.add(
                MovimentacaoEstoque(
                    empresa_id=usuario_a.empresa_id,
                    produto_id=produto_modelo_b.id,
                    usuario_id=usuario_a.id,
                    tipo="entrada",
                    quantidade=1,
                    quantidade_anterior=10,
                    quantidade_atual=11,
                    nome_produto=produto_modelo_b.nome,
                    codigo_barras=produto_modelo_b.codigo_barras,
                    nome_usuario=usuario_a.nome,
                    origem="teste",
                )
            )
            sessao.commit()
        sessao.rollback()

        with pytest.raises(IntegrityError):
            sessao.add(
                ItemVenda(
                    empresa_id=usuario_a.empresa_id,
                    venda_id=venda_a["id"],
                    produto_id=produto_modelo_b.id,
                    codigo_barras=produto_modelo_b.codigo_barras,
                    nome_produto=produto_modelo_b.nome,
                    quantidade=1,
                    valor_unitario=30,
                    valor_total=30,
                    custo_unitario=12,
                    custo_total=12,
                )
            )
            sessao.commit()
        sessao.rollback()

    with motor_banco.connect() as conexao:
        versao = conexao.scalar(
            text(
                "SELECT versao FROM schema_migrations "
                "WHERE versao = '20260609_integridade_multitenant_v1'"
            )
        )
    assert versao == "20260609_integridade_multitenant_v1"
    nomes_indices = {
        indice["name"]
        for indice in inspect(motor_banco).get_indexes("stock_movements")
    }
    assert "ix_stock_movements_empresa_produto_data" in nomes_indices


def test_schema_novo_possui_chaves_compostas_multiempresa():
    motor_temporario = create_engine("sqlite:///:memory:")

    @event.listens_for(motor_temporario, "connect")
    def ativar_chaves_estrangeiras(conexao, _):
        conexao.execute("PRAGMA foreign_keys=ON")

    BaseModelo.metadata.create_all(motor_temporario)
    inspetor = inspect(motor_temporario)
    chaves_itens = {
        (
            tuple(chave["constrained_columns"]),
            chave["referred_table"],
            tuple(chave["referred_columns"]),
        )
        for chave in inspetor.get_foreign_keys("sale_items")
    }
    chaves_movimentos = {
        (
            tuple(chave["constrained_columns"]),
            chave["referred_table"],
            tuple(chave["referred_columns"]),
        )
        for chave in inspetor.get_foreign_keys("stock_movements")
    }

    assert (
        ("venda_id", "empresa_id"),
        "sales",
        ("id", "empresa_id"),
    ) in chaves_itens
    assert (
        ("produto_id", "empresa_id"),
        "products",
        ("id", "empresa_id"),
    ) in chaves_itens
    assert (
        ("usuario_id", "empresa_id"),
        "users",
        ("id", "empresa_id"),
    ) in chaves_movimentos
    assert (
        ("venda_id", "empresa_id"),
        "sales",
        ("id", "empresa_id"),
    ) in chaves_movimentos
    chaves_clientes = {
        (
            tuple(chave["constrained_columns"]),
            chave["referred_table"],
            tuple(chave["referred_columns"]),
        )
        for chave in inspetor.get_foreign_keys("customers")
    }
    assert (
        ("usuario_id", "empresa_id"),
        "users",
        ("id", "empresa_id"),
    ) in chaves_clientes
    motor_temporario.dispose()


def test_usuarios_internos_permissoes_auditoria_e_vendas_por_caixa():
    identificador = uuid4().hex
    email_admin = f"admin-equipe-{identificador}@novaris.one"
    email_caixa = f"caixa-{identificador}@novaris.one"
    cadastro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Empresa com Equipe",
            "nome_usuario": "Administrador Principal",
            "email": email_admin,
            "senha": "SenhaForte123",
        },
    )
    cabecalho_admin = {
        "Authorization": f"Bearer {cadastro.json()['token_acesso']}"
    }

    catalogo = cliente.get(
        "/usuarios/permissoes",
        headers=cabecalho_admin,
    )
    assert catalogo.status_code == 200
    permissoes_caixa = [
        *catalogo.json()["predefinicoes_cargos"]["Caixa"],
        "estoque_movimentar",
        "estoque_gerenciar",
        "financeiro_lancar",
    ]
    criacao_caixa = cliente.post(
        "/usuarios",
        headers=cabecalho_admin,
        json={
            "nome": "Caixa Um",
            "email": email_caixa,
            "senha": "SenhaCaixa123",
            "cargo": "Caixa",
            "permissoes": permissoes_caixa,
        },
    )
    assert criacao_caixa.status_code == 201
    assert criacao_caixa.json()["cargo"] == "Caixa"

    produto = cliente.post(
        "/estoque/produtos",
        headers=cabecalho_admin,
        json={
            "codigo_barras": f"CAIXA-{identificador}",
            "nome": "Produto do Caixa",
            "quantidade": 5,
            "estoque_minimo": 6,
            "preco": 15,
            "preco_compra": 6,
        },
    )
    assert produto.status_code == 201

    login_caixa = cliente.post(
        "/auth/login",
        json={"email": email_caixa, "senha": "SenhaCaixa123"},
    )
    assert login_caixa.status_code == 200
    cabecalho_caixa = {
        "Authorization": f"Bearer {login_caixa.json()['token_acesso']}"
    }
    dados_caixa = cliente.get("/auth/me", headers=cabecalho_caixa).json()
    assert dados_caixa["cargo"] == "Caixa"
    assert "vendas_operar" in dados_caixa["permissoes"]
    assert "estoque_gerenciar" not in dados_caixa["permissoes"]
    assert "financeiro_visualizar" not in dados_caixa["permissoes"]
    assert "financeiro_lancar" in dados_caixa["permissoes"]
    assert cliente.post(
        "/estoque/produtos",
        headers=cabecalho_caixa,
        json={
            "codigo_barras": f"BLOQUEADO-{identificador}",
            "nome": "Produto bloqueado",
            "quantidade": 1,
            "estoque_minimo": 0,
            "preco": 10,
            "preco_compra": 5,
        },
    ).status_code == 403
    assert cliente.put(
        f"/estoque/produtos/{produto.json()['id']}",
        headers=cabecalho_caixa,
        json={
            "codigo_barras": produto.json()["codigo_barras"],
            "nome": "Produto alterado indevidamente",
            "estoque_minimo": 1,
            "preco": 20,
            "preco_compra": 8,
        },
    ).status_code == 403
    assert cliente.delete(
        f"/estoque/produtos/{produto.json()['id']}",
        headers=cabecalho_caixa,
    ).status_code == 403
    dashboard_caixa = cliente.get(
        "/dashboard",
        headers=cabecalho_caixa,
    )
    assert dashboard_caixa.status_code == 200
    assert dashboard_caixa.json()["produtos_estoque_baixo"] == 0
    assert dashboard_caixa.json()["unidades_para_repor"] == 0
    pesquisa_nome = cliente.get(
        "/vendas/produtos/pesquisa",
        headers=cabecalho_caixa,
        params={"nome": "Produto do"},
    )
    assert pesquisa_nome.status_code == 200
    assert pesquisa_nome.json()[0]["codigo_barras"] == produto.json()["codigo_barras"]

    assert cliente.get(
        "/financeiro/resumo",
        headers=cabecalho_caixa,
    ).status_code == 403
    assert cliente.get(
        "/usuarios",
        headers=cabecalho_caixa,
    ).status_code == 403

    movimentacao = cliente.post(
        f"/estoque/produtos/{produto.json()['id']}/movimentacoes",
        headers=cabecalho_caixa,
        json={"tipo": "entrada", "quantidade": 4},
    )
    assert movimentacao.status_code == 200
    lancamento = cliente.post(
        "/financeiro/lancamentos",
        headers=cabecalho_caixa,
        json={
            "tipo": "entrada",
            "categoria": "Ajuste",
            "descricao": "Entrada registrada pelo caixa",
            "valor": 12,
        },
    )
    assert lancamento.status_code == 201

    abrir_caixa_teste(cabecalho_caixa, 50)
    caixas_antes_venda = cliente.get(
        "/caixa/ativos",
        headers=cabecalho_admin,
    )
    assert caixas_antes_venda.status_code == 200
    assert caixas_antes_venda.json()[0]["nome_usuario"] == "Caixa Um"
    assert cliente.get(
        "/caixa/ativos",
        headers=cabecalho_caixa,
    ).status_code == 403
    venda = cliente.post(
        "/vendas",
        headers=cabecalho_caixa,
        json={
            "itens": [{
                "codigo_barras": produto.json()["codigo_barras"],
                "quantidade": 2,
            }],
            "desconto": 3,
            "forma_pagamento": "dinheiro",
        },
    )
    assert venda.status_code == 201
    comprovante_caixa = cliente.get(
        f"/vendas/{venda.json()['id']}/comprovante",
        headers=cabecalho_caixa,
    )
    assert comprovante_caixa.status_code == 200
    vendas_recentes = cliente.get(
        "/vendas/recentes",
        headers=cabecalho_caixa,
    )
    assert vendas_recentes.status_code == 200
    assert vendas_recentes.json()[0]["id"] == venda.json()["id"]
    assert vendas_recentes.json()[0]["nome_usuario"] == "Caixa Um"
    caixas_depois_venda = cliente.get(
        "/caixa/ativos",
        headers=cabecalho_admin,
    ).json()
    assert caixas_depois_venda[0]["total_vendido"] == "27.00"
    fluxo = cliente.get(
        "/financeiro/fluxo-caixa",
        headers=cabecalho_admin,
    )
    assert fluxo.status_code == 200
    movimento_venda = next(
        item
        for item in fluxo.json()
        if item["id"] == f"venda-{venda.json()['id']}"
    )
    assert movimento_venda["nome_usuario"] == "Caixa Um"
    assert movimento_venda["caixa_id"] == caixas_depois_venda[0]["id"]

    resumo = cliente.get(
        "/vendas/resumo-operadores",
        headers=cabecalho_admin,
    )
    assert resumo.status_code == 200
    linha_caixa = next(
        item
        for item in resumo.json()
        if item["usuario_id"] == criacao_caixa.json()["id"]
    )
    assert linha_caixa["nome_usuario"] == "Caixa Um"
    assert linha_caixa["quantidade_vendas"] == 1
    assert linha_caixa["total_vendido"] == "27.00"
    assert linha_caixa["total_descontos"] == "3.00"
    assert linha_caixa["formas_pagamento"]["dinheiro"] == "27.00"

    desempenho = cliente.get(
        "/usuarios/desempenho",
        headers=cabecalho_admin,
        params={"usuario_id": criacao_caixa.json()["id"]},
    )
    assert desempenho.status_code == 200
    dados_desempenho = desempenho.json()[0]
    assert dados_desempenho["quantidade_vendas"] == 1
    assert dados_desempenho["total_vendido"] == "27.00"
    assert dados_desempenho["movimentacoes_estoque"] == 2
    assert dados_desempenho["entradas_estoque"] == 1
    assert dados_desempenho["saidas_estoque"] == 1
    assert dados_desempenho["unidades_entrada"] == 4
    assert dados_desempenho["unidades_saida"] == 2
    assert dados_desempenho["lancamentos_financeiros"] == 1
    assert dados_desempenho["entradas_financeiras"] == "12.00"
    assert dados_desempenho["saidas_financeiras"] == "0.00"

    vendas_caixa = cliente.get(
        "/vendas",
        headers=cabecalho_admin,
        params={"usuario_id": criacao_caixa.json()["id"]},
    )
    assert vendas_caixa.status_code == 200
    assert len(vendas_caixa.json()) == 1
    assert vendas_caixa.json()[0]["nome_usuario"] == "Caixa Um"

    logs = cliente.get(
        "/usuarios/auditoria/logs",
        headers=cabecalho_admin,
    )
    assert logs.status_code == 200
    acoes = {log["acao"] for log in logs.json()}
    assert "usuario_criado" in acoes
    assert "venda_registrada" in acoes

    outro_cadastro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Outra Empresa",
            "nome_usuario": "Outro Admin",
            "email": f"outro-{identificador}@novaris.one",
            "senha": "SenhaForte123",
        },
    )
    cabecalho_outro = {
        "Authorization": f"Bearer {outro_cadastro.json()['token_acesso']}"
    }
    usuarios_outro = cliente.get("/usuarios", headers=cabecalho_outro).json()
    assert {usuario["email"] for usuario in usuarios_outro} == {
        f"outro-{identificador}@novaris.one"
    }
    desempenho_outro = cliente.get(
        "/usuarios/desempenho",
        headers=cabecalho_outro,
        params={"usuario_id": criacao_caixa.json()["id"]},
    )
    assert desempenho_outro.status_code == 200
    assert desempenho_outro.json() == []


def test_abertura_fechamento_caixa_e_bloqueio_de_vendas():
    identificador = uuid4().hex
    cadastro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Loja Fechamento",
            "nome_usuario": "Caixa Responsavel",
            "email": f"fechamento-{identificador}@novaris.one",
            "senha": "SenhaForte123",
        },
    )
    cabecalho = {
        "Authorization": f"Bearer {cadastro.json()['token_acesso']}"
    }
    produto = cliente.post(
        "/estoque/produtos",
        headers=cabecalho,
        json={
            "codigo_barras": f"CX-{identificador}",
            "nome": "Produto do Fechamento",
            "quantidade": 20,
            "estoque_minimo": 2,
            "preco": 10,
            "preco_compra": 4,
        },
    ).json()

    bloqueada = cliente.post(
        "/vendas",
        headers=cabecalho,
        json={
            "itens": [{
                "codigo_barras": produto["codigo_barras"],
                "quantidade": 1,
            }],
            "forma_pagamento": "dinheiro",
        },
    )
    assert bloqueada.status_code == 409

    caixa = abrir_caixa_teste(cabecalho, 100)
    assert caixa["status"] == "aberto"
    assert caixa["valor_esperado"] == "100.00"
    duplicado = cliente.post(
        "/caixa/abrir",
        headers=cabecalho,
        json={"valor_inicial": 50},
    )
    assert duplicado.status_code == 409

    configuracao = cliente.put(
        "/pagamentos/configuracao",
        headers=cabecalho,
        json={
            "provedor": "manual",
            "chave_pix": f"caixa-{identificador}@pix",
            "ativo": True,
        },
    )
    assert configuracao.status_code == 200

    vendas = {}
    for forma, desconto in [
        ("dinheiro", 2),
        ("debito", 0),
        ("credito", 0),
        ("pix", 0),
    ]:
        resposta = cliente.post(
            "/vendas",
            headers=cabecalho,
            json={
                "itens": [{
                    "codigo_barras": produto["codigo_barras"],
                    "quantidade": 1,
                }],
                "desconto": desconto,
                "forma_pagamento": forma,
            },
        )
        assert resposta.status_code == 201
        vendas[forma] = resposta.json()

    fechamento_pendente = cliente.post(
        "/caixa/fechar",
        headers=cabecalho,
        json={"valor_real": 108},
    )
    assert fechamento_pendente.status_code == 409

    confirmacao = cliente.post(
        f"/vendas/{vendas['pix']['id']}/confirmar-pagamento",
        headers=cabecalho,
    )
    assert confirmacao.status_code == 200

    resumo = cliente.get("/caixa/atual", headers=cabecalho).json()
    assert resumo["quantidade_vendas"] == 4
    assert resumo["total_dinheiro"] == "8.00"
    assert resumo["total_pix"] == "10.00"
    assert resumo["total_debito"] == "10.00"
    assert resumo["total_credito"] == "10.00"
    assert resumo["total_descontos"] == "2.00"
    assert resumo["valor_esperado"] == "108.00"

    fechamento = cliente.post(
        "/caixa/fechar",
        headers=cabecalho,
        json={"valor_real": 110},
    )
    assert fechamento.status_code == 200
    dados = fechamento.json()
    assert dados["status"] == "fechado"
    assert dados["diferenca"] == "2.00"
    assert dados["situacao_diferenca"] == "sobra"
    assert dados["data_fechamento"] is not None

    assert cliente.get("/caixa/atual", headers=cabecalho).json() is None
    nova_venda_bloqueada = cliente.post(
        "/vendas",
        headers=cabecalho,
        json={
            "itens": [{
                "codigo_barras": produto["codigo_barras"],
                "quantidade": 1,
            }],
            "forma_pagamento": "dinheiro",
        },
    )
    assert nova_venda_bloqueada.status_code == 409

    relatorio = cliente.get(
        f"/caixa/{dados['id']}/relatorio",
        headers=cabecalho,
    )
    assert relatorio.status_code == 200
    assert relatorio.content.startswith(b"%PDF")

    logs = cliente.get(
        "/usuarios/auditoria/logs",
        headers=cabecalho,
    ).json()
    acoes = {log["acao"] for log in logs}
    assert "caixa_aberto" in acoes
    assert "caixa_fechado" in acoes


def test_cancelamento_estorna_venda_e_preserva_auditoria():
    identificador = uuid4().hex
    cadastro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Loja de Estornos",
            "nome_usuario": "Administrador Estorno",
            "email": f"admin-estorno-{identificador}@novaris.one",
            "senha": "SenhaForte123",
        },
    )
    cabecalho_admin = {
        "Authorization": f"Bearer {cadastro.json()['token_acesso']}"
    }
    catalogo = cliente.get(
        "/usuarios/permissoes",
        headers=cabecalho_admin,
    ).json()
    assert "vendas_cancelar" in catalogo["permissoes"]

    email_caixa = f"caixa-estorno-{identificador}@novaris.one"
    caixa_criado = cliente.post(
        "/usuarios",
        headers=cabecalho_admin,
        json={
            "nome": "Caixa do Estorno",
            "email": email_caixa,
            "senha": "SenhaCaixa123",
            "cargo": "Caixa",
            "permissoes": catalogo["predefinicoes_cargos"]["Caixa"],
        },
    )
    assert caixa_criado.status_code == 201
    assert "vendas_cancelar" not in caixa_criado.json()["permissoes"]

    produto = cliente.post(
        "/estoque/produtos",
        headers=cabecalho_admin,
        json={
            "codigo_barras": f"ESTORNO-{identificador}",
            "nome": "Produto para Estorno",
            "quantidade": 10,
            "estoque_minimo": 2,
            "preco": 20,
            "preco_compra": 8,
        },
    ).json()
    login_caixa = cliente.post(
        "/auth/login",
        json={"email": email_caixa, "senha": "SenhaCaixa123"},
    )
    cabecalho_caixa = {
        "Authorization": f"Bearer {login_caixa.json()['token_acesso']}"
    }
    caixa = abrir_caixa_teste(cabecalho_caixa, 100)
    venda = cliente.post(
        "/vendas",
        headers=cabecalho_caixa,
        json={
            "itens": [{
                "codigo_barras": produto["codigo_barras"],
                "quantidade": 2,
            }],
            "forma_pagamento": "dinheiro",
        },
    )
    assert venda.status_code == 201
    venda_id = venda.json()["id"]

    sem_permissao = cliente.post(
        f"/vendas/{venda_id}/cancelar",
        headers=cabecalho_caixa,
        json={"motivo": "Tentativa sem permissao"},
    )
    assert sem_permissao.status_code == 403

    outro_cadastro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Empresa sem Acesso ao Estorno",
            "nome_usuario": "Outro Administrador",
            "email": f"outro-estorno-{identificador}@novaris.one",
            "senha": "SenhaForte123",
        },
    )
    cabecalho_outro = {
        "Authorization": f"Bearer {outro_cadastro.json()['token_acesso']}"
    }
    cruzado = cliente.post(
        f"/vendas/{venda_id}/cancelar",
        headers=cabecalho_outro,
        json={"motivo": "Tentativa de outra empresa"},
    )
    assert cruzado.status_code == 404

    produtos_antes = cliente.get(
        "/estoque/produtos",
        headers=cabecalho_admin,
    ).json()
    assert next(
        item for item in produtos_antes if item["id"] == produto["id"]
    )["quantidade"] == 8
    assert cliente.get(
        "/financeiro/resumo",
        headers=cabecalho_admin,
    ).json()["faturamento"] == "40.00"

    cancelamento = cliente.post(
        f"/vendas/{venda_id}/cancelar",
        headers=cabecalho_admin,
        json={"motivo": "Cliente desistiu da compra"},
    )
    assert cancelamento.status_code == 200
    dados_cancelamento = cancelamento.json()
    assert dados_cancelamento["status"] == "cancelado"
    assert dados_cancelamento["produtos_devolvidos"] == 2
    assert dados_cancelamento["motivo"] == "Cliente desistiu da compra"
    assert dados_cancelamento["data_cancelamento"] is not None

    produtos_depois = cliente.get(
        "/estoque/produtos",
        headers=cabecalho_admin,
    ).json()
    assert next(
        item for item in produtos_depois if item["id"] == produto["id"]
    )["quantidade"] == 10

    historico = cliente.get(
        "/estoque/movimentacoes",
        headers=cabecalho_admin,
        params={"busca": produto["codigo_barras"]},
    ).json()
    movimento_estorno = next(
        item for item in historico
        if item["origem"] == "cancelamento_venda"
    )
    assert movimento_estorno["tipo"] == "entrada"
    assert movimento_estorno["quantidade"] == 2
    assert movimento_estorno["quantidade_anterior"] == 8
    assert movimento_estorno["quantidade_atual"] == 10
    assert movimento_estorno["nome_usuario"] == "Administrador Estorno"

    resumo_financeiro = cliente.get(
        "/financeiro/resumo",
        headers=cabecalho_admin,
    ).json()
    assert resumo_financeiro["faturamento"] == "0.00"
    assert resumo_financeiro["quantidade_vendas"] == 0
    dashboard = cliente.get(
        "/dashboard",
        headers=cabecalho_admin,
    ).json()
    assert dashboard["faturamento_mensal"] == 0
    assert dashboard["quantidade_vendas"] == 0

    fluxo = cliente.get(
        "/financeiro/fluxo-caixa",
        headers=cabecalho_admin,
    ).json()
    venda_fluxo = next(
        item for item in fluxo if item["id"] == f"venda-{venda_id}"
    )
    estorno_fluxo = next(
        item for item in fluxo if item["id"] == f"estorno-{venda_id}"
    )
    assert venda_fluxo["tipo"] == "entrada"
    assert estorno_fluxo["tipo"] == "saida"
    assert estorno_fluxo["categoria"] == "Estornos"
    assert estorno_fluxo["valor"] == "40.00"
    assert estorno_fluxo["nome_usuario"] == "Administrador Estorno"

    caixa_atual = cliente.get(
        "/caixa/atual",
        headers=cabecalho_caixa,
    ).json()
    assert caixa_atual["quantidade_vendas"] == 0
    assert caixa_atual["quantidade_cancelamentos"] == 1
    assert caixa_atual["total_cancelamentos"] == "40.00"
    assert caixa_atual["valor_esperado"] == "100.00"

    vendas_recentes = cliente.get(
        "/vendas/recentes",
        headers=cabecalho_admin,
    ).json()
    venda_cancelada = next(
        item for item in vendas_recentes if item["id"] == venda_id
    )
    assert venda_cancelada["status"] == "cancelado"
    assert venda_cancelada["motivo_cancelamento"] == (
        "Cliente desistiu da compra"
    )
    assert venda_cancelada["nome_usuario_cancelamento"] == (
        "Administrador Estorno"
    )

    duplicado = cliente.post(
        f"/vendas/{venda_id}/cancelar",
        headers=cabecalho_admin,
        json={"motivo": "Segunda tentativa de cancelamento"},
    )
    assert duplicado.status_code == 409

    with SessaoBanco() as sessao:
        venda_salva = sessao.scalar(
            select(Venda).where(Venda.id == venda_id)
        )
        registro = sessao.scalar(
            select(CancelamentoVenda).where(
                CancelamentoVenda.venda_id == venda_id
            )
        )
        assert venda_salva.status == "cancelado"
        assert len(venda_salva.itens) == 1
        assert registro.motivo == "Cliente desistiu da compra"
        assert registro.usuario_id == dados_cancelamento["usuario_id"]

    logs = cliente.get(
        "/usuarios/auditoria/logs",
        headers=cabecalho_admin,
    ).json()
    assert any(
        log["acao"] == "venda_cancelada"
        and log["entidade_id"] == venda_id
        for log in logs
    )


def test_trocas_devolucoes_caixa_relatorios_e_backup_multiempresa():
    identificador = uuid4().hex
    cadastro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Loja Operacoes Avancadas",
            "nome_usuario": "Administrador Operacoes",
            "email": f"operacoes-{identificador}@novaris.one",
            "senha": "SenhaForte123",
        },
    )
    cabecalho = {
        "Authorization": f"Bearer {cadastro.json()['token_acesso']}"
    }
    produto_a = cliente.post(
        "/estoque/produtos",
        headers=cabecalho,
        json={
            "codigo_barras": f"A-{identificador}",
            "nome": "Produto A",
            "categoria": "Bebidas",
            "quantidade": 10,
            "estoque_minimo": 2,
            "preco": 20,
            "preco_compra": 8,
        },
    ).json()
    produto_b = cliente.post(
        "/estoque/produtos",
        headers=cabecalho,
        json={
            "codigo_barras": f"B-{identificador}",
            "nome": "Produto B",
            "categoria": "Bebidas",
            "quantidade": 5,
            "estoque_minimo": 1,
            "preco": 30,
            "preco_compra": 10,
        },
    ).json()
    abrir_caixa_teste(cabecalho, 100)
    venda = cliente.post(
        "/vendas",
        headers=cabecalho,
        json={
            "itens": [{
                "codigo_barras": produto_a["codigo_barras"],
                "quantidade": 3,
            }],
            "forma_pagamento": "dinheiro",
        },
    )
    assert venda.status_code == 201
    venda_id = venda.json()["id"]

    sangria = cliente.post(
        "/caixa/sangria",
        headers=cabecalho,
        json={"valor": 10, "motivo": "Pagamento de entrega local"},
    )
    reforco = cliente.post(
        "/caixa/reforco",
        headers=cabecalho,
        json={"valor": 5, "motivo": "Adicao de moedas para troco"},
    )
    assert sangria.status_code == 200
    assert reforco.status_code == 200

    detalhe = cliente.get(
        f"/operacoes-venda/vendas/{venda_id}",
        headers=cabecalho,
    )
    assert detalhe.status_code == 200
    item_venda_id = detalhe.json()["itens"][0]["id"]
    devolucao = cliente.post(
        f"/operacoes-venda/vendas/{venda_id}",
        headers=cabecalho,
        json={
            "tipo": "devolucao",
            "motivo": "Cliente devolveu uma unidade fechada",
            "itens_devolvidos": [{
                "item_venda_id": item_venda_id,
                "quantidade": 1,
            }],
            "itens_novos": [],
            "forma_pagamento": "dinheiro",
        },
    )
    assert devolucao.status_code == 201
    assert devolucao.json()["valor_estornado"] == "20.00"

    troca = cliente.post(
        f"/operacoes-venda/vendas/{venda_id}",
        headers=cabecalho,
        json={
            "tipo": "troca",
            "motivo": "Cliente escolheu outro produto",
            "itens_devolvidos": [{
                "item_venda_id": item_venda_id,
                "quantidade": 1,
            }],
            "itens_novos": [{
                "codigo_barras": produto_b["codigo_barras"],
                "quantidade": 1,
            }],
            "forma_pagamento": "dinheiro",
        },
    )
    assert troca.status_code == 201
    assert troca.json()["credito_devolvido"] == "20.00"
    assert troca.json()["valor_novos_itens"] == "30.00"
    assert troca.json()["valor_adicional"] == "10.00"

    detalhe_depois = cliente.get(
        f"/operacoes-venda/vendas/{venda_id}",
        headers=cabecalho,
    ).json()
    assert detalhe_depois["itens"][0]["quantidade_ja_devolvida"] == 2
    assert detalhe_depois["itens"][0]["quantidade_disponivel_devolucao"] == 1
    produtos = cliente.get("/estoque/produtos", headers=cabecalho).json()
    saldos = {item["id"]: item["quantidade"] for item in produtos}
    assert saldos[produto_a["id"]] == 9
    assert saldos[produto_b["id"]] == 4

    caixa = cliente.get("/caixa/atual", headers=cabecalho).json()
    assert caixa["total_sangrias"] == "10.00"
    assert caixa["total_reforcos"] == "5.00"
    assert caixa["total_devolucoes"] == "20.00"
    assert caixa["total_adicionais_troca"] == "10.00"
    assert caixa["valor_esperado"] == "145.00"

    financeiro = cliente.get("/financeiro/resumo", headers=cabecalho).json()
    assert financeiro["faturamento"] == "50.00"
    assert financeiro["custo_produtos"] == "18.00"
    assert financeiro["lucro_bruto"] == "32.00"
    fluxo = cliente.get("/financeiro/fluxo-caixa", headers=cabecalho).json()
    origens = {item["origem"] for item in fluxo}
    assert {"venda", "devolucao", "troca", "caixa"} <= origens

    relatorio = cliente.get(
        "/relatorios/vendas",
        headers=cabecalho,
        params={"periodo": "mes", "categoria": "Bebidas"},
    )
    assert relatorio.status_code == 200
    assert relatorio.json()["faturamento"] == "50.00"
    assert relatorio.json()["lucro"] == "32.00"
    assert relatorio.json()["quantidade_vendida"] == 2
    assert cliente.get(
        "/relatorios/vendas/pdf",
        headers=cabecalho,
    ).content.startswith(b"%PDF")
    assert cliente.get(
        "/relatorios/vendas/excel",
        headers=cabecalho,
    ).content.startswith(b"PK")

    backup = cliente.post("/backups", headers=cabecalho)
    assert backup.status_code == 201
    backup_id = backup.json()["id"]
    cliente.post(
        f"/estoque/produtos/{produto_a['id']}/movimentacoes",
        headers=cabecalho,
        json={"tipo": "entrada", "quantidade": 5},
    )
    restauracao = cliente.post(
        f"/backups/{backup_id}/restaurar",
        headers=cabecalho,
    )
    assert restauracao.status_code == 200
    produtos_restaurados = cliente.get(
        "/estoque/produtos",
        headers=cabecalho,
    ).json()
    assert next(
        item for item in produtos_restaurados if item["id"] == produto_a["id"]
    )["quantidade"] == 9

    outro = cliente.post(
        "/auth/register",
        json={
            "nome_empresa": "Outra Empresa Backup",
            "nome_usuario": "Outro Administrador Backup",
            "email": f"outro-backup-{identificador}@novaris.one",
            "senha": "SenhaForte123",
        },
    )
    cabecalho_outro = {
        "Authorization": f"Bearer {outro.json()['token_acesso']}"
    }
    assert cliente.get(
        f"/backups/{backup_id}/download",
        headers=cabecalho_outro,
    ).status_code == 404
    assert cliente.post(
        f"/backups/{backup_id}/restaurar",
        headers=cabecalho_outro,
    ).status_code == 404

    logs = cliente.get(
        "/usuarios/auditoria/logs",
        headers=cabecalho,
    ).json()
    acoes = {item["acao"] for item in logs}
    assert {
        "caixa_sangria",
        "caixa_reforco",
        "devolucao_realizada",
        "troca_realizada",
        "backup_criado",
        "backup_restaurado",
    } <= acoes
