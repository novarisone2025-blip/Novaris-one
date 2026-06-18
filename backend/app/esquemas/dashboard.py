from pydantic import BaseModel, Field


class ProdutoMaisVendido(BaseModel):
    nome: str
    codigo_barras: str
    quantidade: int
    faturamento: float


class FaturamentoDia(BaseModel):
    data: str
    valor: float


class ClienteDestaque(BaseModel):
    cliente_id: int
    nome: str
    total_gasto: float
    quantidade_compras: int


class DashboardResposta(BaseModel):
    nome_empresa: str
    nome_usuario: str
    total_clientes: int = 0
    total_produtos: int = 0
    total_vendas: float = 0
    lucro_mensal: float = 0
    produtos_estoque_baixo: int = 0
    unidades_para_repor: int = 0
    faturamento_diario: float = 0
    faturamento_semanal: float = 0
    faturamento_mensal: float = 0
    quantidade_vendas: int = 0
    ticket_medio: float = 0
    margem_bruta: float = 0
    produtos_proximos_reposicao: int = 0
    pedidos_compra_pendentes: int = 0
    orcamentos_pendentes: int = 0
    taxa_conversao_orcamentos: float = 0
    clientes_mais_compram: list[ClienteDestaque] = Field(default_factory=list)
    produtos_mais_vendidos: list[ProdutoMaisVendido] = Field(
        default_factory=list
    )
    faturamento_ultimos_dias: list[FaturamentoDia] = Field(
        default_factory=list
    )
