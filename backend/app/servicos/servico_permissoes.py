import json

from fastapi import HTTPException

from app.modelos.usuario import Usuario


PERMISSOES_DISPONIVEIS = {
    "dashboard_visualizar": "Visualizar dashboard",
    "vendas_operar": "Operar o PDV",
    "vendas_relatorios": "Visualizar vendas e relatorios por caixa",
    "vendas_cancelar": "Cancelar e estornar vendas finalizadas",
    "vendas_devolver": "Realizar trocas e devolucoes",
    "estoque_visualizar": "Visualizar estoque e historico",
    "estoque_movimentar": "Registrar entradas e saidas",
    "estoque_gerenciar": "Cadastrar, editar e excluir produtos",
    "produtos_cadastrar": "Cadastrar produtos",
    "produtos_editar": "Editar produtos",
    "produtos_excluir": "Excluir produtos",
    "fornecedores_gerenciar": "Gerenciar fornecedores",
    "compras_visualizar": "Visualizar compras e sugestoes de reposicao",
    "compras_gerenciar": "Criar, enviar, receber e cancelar pedidos de compra",
    "clientes_visualizar": "Visualizar clientes e historico de compras",
    "clientes_gerenciar": "Cadastrar e editar clientes",
    "clientes_relatorios": "Exportar relatorios de clientes",
    "orcamentos_visualizar": "Visualizar e compartilhar orcamentos",
    "orcamentos_gerenciar": "Criar e cancelar orcamentos",
    "orcamentos_converter": "Converter orcamentos em vendas",
    "financeiro_visualizar": "Visualizar financeiro",
    "financeiro_lancar": "Criar lancamentos financeiros",
    "pagamentos_gerenciar": "Gerenciar configuracoes de pagamento",
    "caixas_ativos_visualizar": "Visualizar caixas abertos da empresa",
    "caixa_sangria": "Realizar sangrias no caixa",
    "caixa_reforco": "Realizar reforcos no caixa",
    "relatorios_gerar": "Gerar relatorios PDF e Excel",
    "relatorios_financeiros": "Acessar relatorios financeiros avancados",
    "usuarios_gerenciar": "Gerenciar usuarios e permissoes",
    "auditoria_visualizar": "Visualizar logs de auditoria",
    "backup_gerenciar": "Criar e restaurar backups da empresa",
}

TODAS_PERMISSOES = list(PERMISSOES_DISPONIVEIS)

PERMISSOES_POR_CARGO = {
    "Administrador": TODAS_PERMISSOES,
    "Gerente": [
        permissao
        for permissao in TODAS_PERMISSOES
        if permissao not in {
            "usuarios_gerenciar",
            "pagamentos_gerenciar",
            "caixas_ativos_visualizar",
            "backup_gerenciar",
        }
    ],
    "Caixa": [
        "dashboard_visualizar",
        "vendas_operar",
        "clientes_visualizar",
        "clientes_gerenciar",
    ],
    "Estoquista": [
        "dashboard_visualizar",
        "estoque_visualizar",
        "estoque_movimentar",
        "estoque_gerenciar",
        "produtos_cadastrar",
        "produtos_editar",
        "produtos_excluir",
        "fornecedores_gerenciar",
        "compras_visualizar",
        "compras_gerenciar",
        "relatorios_gerar",
    ],
}

RESTRICOES_POR_CARGO = {
    "Caixa": {
        "estoque_gerenciar",
        "produtos_cadastrar",
        "produtos_editar",
        "produtos_excluir",
        "caixas_ativos_visualizar",
    },
    "Gerente": {"caixas_ativos_visualizar"},
    "Estoquista": {"caixas_ativos_visualizar"},
}

CARGOS_ALERTA_ESTOQUE = {"Administrador", "Gerente", "Estoquista", "Estoque"}


def normalizar_permissoes_cargo(
    permissoes: list[str],
    cargo: str,
) -> list[str]:
    restritas = RESTRICOES_POR_CARGO.get(cargo, set())
    normalizadas = [
        permissao
        for permissao in permissoes
        if permissao not in restritas
    ]
    if (
        cargo == "Administrador"
        and "caixas_ativos_visualizar" not in normalizadas
    ):
        normalizadas.append("caixas_ativos_visualizar")
    if (
        cargo == "Administrador"
        and "vendas_cancelar" not in normalizadas
    ):
        normalizadas.append("vendas_cancelar")
    return normalizadas


def permissoes_do_usuario(usuario: Usuario) -> list[str]:
    if usuario.tipo_usuario == "admin":
        permissoes_validas = TODAS_PERMISSOES.copy()
    else:
        try:
            permissoes = json.loads(usuario.permissoes or "[]")
        except json.JSONDecodeError:
            return []
        permissoes_validas = [
            permissao
            for permissao in permissoes
            if permissao in PERMISSOES_DISPONIVEIS
        ]
    return normalizar_permissoes_cargo(
        permissoes_validas,
        usuario.cargo,
    )


def serializar_permissoes(permissoes: list[str]) -> str:
    invalidas = set(permissoes) - set(PERMISSOES_DISPONIVEIS)
    if invalidas:
        raise HTTPException(
            422,
            "Permissoes invalidas: " + ", ".join(sorted(invalidas)),
        )
    return json.dumps(sorted(set(permissoes)))


def garantir_permissao(usuario: Usuario, permissao: str) -> None:
    if permissao not in permissoes_do_usuario(usuario):
        raise HTTPException(
            403,
            "Seu usuario nao possui permissao para esta operacao.",
        )


def garantir_uma_das_permissoes(
    usuario: Usuario,
    *permissoes: str,
) -> None:
    atuais = set(permissoes_do_usuario(usuario))
    if not atuais.intersection(permissoes):
        raise HTTPException(
            403,
            "Seu usuario nao possui permissao para esta operacao.",
        )


def pode_visualizar_alertas_estoque(usuario: Usuario) -> bool:
    return usuario.cargo in CARGOS_ALERTA_ESTOQUE


def garantir_visualizacao_alertas_estoque(usuario: Usuario) -> None:
    if not pode_visualizar_alertas_estoque(usuario):
        raise HTTPException(
            403,
            "Alertas de estoque estao disponiveis apenas para a gestao.",
        )
