import { lazy, Suspense, useEffect, useState } from "react";
import {
  CircleDollarSign,
  CalendarDays,
  Package,
  ReceiptText,
  TrendingUp,
  TriangleAlert,
  Users,
  ClipboardList,
  ContactRound,
  PackageCheck,
  ShoppingCart,
} from "lucide-react";

import { CartaoIndicador } from "../componentes/CartaoIndicador";
import { MenuLateral } from "../componentes/MenuLateral";
import { TopoDashboard } from "../componentes/TopoDashboard";
import { usarAutenticacao } from "../contexts/ContextoAutenticacao";
import { buscarDadosDashboard } from "../servicos/servicoApi";

function carregarPagina(importador, nomeExportado) {
  return lazy(() => importador().then((modulo) => ({
    default: modulo[nomeExportado],
  })));
}


const TelaEstoque = carregarPagina(
  () => import("./TelaEstoque"),
  "TelaEstoque",
);
const TelaHistoricoEstoque = carregarPagina(
  () => import("./TelaHistoricoEstoque"),
  "TelaHistoricoEstoque",
);
const TelaVendas = carregarPagina(
  () => import("./TelaVendas"),
  "TelaVendas",
);
const TelaVendasRecentes = carregarPagina(
  () => import("./TelaVendasRecentes"),
  "TelaVendasRecentes",
);
const TelaFinanceiro = carregarPagina(
  () => import("./TelaFinanceiro"),
  "TelaFinanceiro",
);
const TelaFornecedores = carregarPagina(
  () => import("./TelaFornecedores"),
  "TelaFornecedores",
);
const TelaConfiguracoesPagamento = carregarPagina(
  () => import("./TelaConfiguracoesPagamento"),
  "TelaConfiguracoesPagamento",
);
const TelaUsuarios = carregarPagina(
  () => import("./TelaUsuarios"),
  "TelaUsuarios",
);
const TelaCaixasAtivos = carregarPagina(
  () => import("./TelaCaixasAtivos"),
  "TelaCaixasAtivos",
);
const TelaTrocasDevolucoes = carregarPagina(
  () => import("./TelaTrocasDevolucoes"),
  "TelaTrocasDevolucoes",
);
const TelaRelatoriosAvancados = carregarPagina(
  () => import("./TelaRelatoriosAvancados"),
  "TelaRelatoriosAvancados",
);
const TelaBackupSeguranca = carregarPagina(
  () => import("./TelaBackupSeguranca"),
  "TelaBackupSeguranca",
);
const TelaClientes = carregarPagina(
  () => import("./TelaClientes"),
  "TelaClientes",
);
const TelaCompras = carregarPagina(
  () => import("./TelaCompras"),
  "TelaCompras",
);
const TelaOrcamentos = carregarPagina(
  () => import("./TelaOrcamentos"),
  "TelaOrcamentos",
);


const dadosIniciais = {
  nome_empresa: "",
  nome_usuario: "",
  total_clientes: 0,
  total_produtos: 0,
  total_vendas: 0,
  lucro_mensal: 0,
  produtos_estoque_baixo: 0,
  unidades_para_repor: 0,
  faturamento_diario: 0,
  faturamento_semanal: 0,
  faturamento_mensal: 0,
  quantidade_vendas: 0,
  ticket_medio: 0,
  margem_bruta: 0,
  produtos_mais_vendidos: [],
  faturamento_ultimos_dias: [],
  produtos_proximos_reposicao: 0,
  pedidos_compra_pendentes: 0,
  orcamentos_pendentes: 0,
  taxa_conversao_orcamentos: 0,
  clientes_mais_compram: [],
};


export function TelaDashboard() {
  const { usuario } = usarAutenticacao();
  const [dados, definirDados] = useState(dadosIniciais);
  const [menuAberto, definirMenuAberto] = useState(false);
  const [paginaAtual, definirPaginaAtual] = useState("dashboard");
  const [paginasVisitadas, definirPaginasVisitadas] = useState(
    () => new Set(["dashboard"]),
  );

  useEffect(() => {
    carregarDadosIniciais();
  }, []);

  async function carregarDadosIniciais() {
    const resposta = await buscarDadosDashboard();
    definirDados(resposta);
  }

  function navegarPara(pagina) {
    definirPaginasVisitadas((atuais) => {
      if (atuais.has(pagina)) return atuais;
      return new Set([...atuais, pagina]);
    });
    definirPaginaAtual(pagina);
  }

  const formatoMoeda = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
  const podeVerAlertasEstoque = (
    ["Administrador", "Gerente", "Estoquista", "Estoque"].includes(
      usuario?.cargo,
    )
  );

  return (
    <div className="estrutura-dashboard">
      <MenuLateral
        aberto={menuAberto}
        fecharMenu={() => definirMenuAberto(false)}
        paginaAtual={paginaAtual}
        navegarPara={navegarPara}
      />

      <div className="area-dashboard">
        <TopoDashboard abrirMenu={() => definirMenuAberto(true)} />

        <div className="paginas-dashboard-persistentes">
          <Suspense
            fallback={<p className="estado-financeiro">Carregando tela...</p>}
          >
          {paginasVisitadas.has("estoque") && (
            <section
              className="pagina-persistente"
              hidden={paginaAtual !== "estoque"}
            >
              <TelaEstoque aoAlterarEstoque={carregarDadosIniciais} />
            </section>
          )}
          {paginasVisitadas.has("historico") && (
            <section
              className="pagina-persistente"
              hidden={paginaAtual !== "historico"}
            >
              <TelaHistoricoEstoque />
            </section>
          )}
          {paginasVisitadas.has("vendas") && (
            <section
              className="pagina-persistente"
              hidden={paginaAtual !== "vendas"}
            >
              <TelaVendas aoRegistrarVenda={carregarDadosIniciais} />
            </section>
          )}
          {paginasVisitadas.has("vendas-recentes") && (
            <section
              className="pagina-persistente"
              hidden={paginaAtual !== "vendas-recentes"}
            >
              <TelaVendasRecentes aoAlterar={carregarDadosIniciais} />
            </section>
          )}
          {paginasVisitadas.has("fornecedores") && (
            <section
              className="pagina-persistente"
              hidden={paginaAtual !== "fornecedores"}
            >
              <TelaFornecedores />
            </section>
          )}
          {paginasVisitadas.has("compras") && (
            <section
              className="pagina-persistente"
              hidden={paginaAtual !== "compras"}
            >
              <TelaCompras aoAlterar={carregarDadosIniciais} />
            </section>
          )}
          {paginasVisitadas.has("clientes") && (
            <section
              className="pagina-persistente"
              hidden={paginaAtual !== "clientes"}
            >
              <TelaClientes />
            </section>
          )}
          {paginasVisitadas.has("orcamentos") && (
            <section
              className="pagina-persistente"
              hidden={paginaAtual !== "orcamentos"}
            >
              <TelaOrcamentos aoAlterar={carregarDadosIniciais} />
            </section>
          )}
          {paginasVisitadas.has("financeiro") && (
            <section
              className="pagina-persistente"
              hidden={paginaAtual !== "financeiro"}
            >
              <TelaFinanceiro
                aoAlterarFinanceiro={carregarDadosIniciais}
              />
            </section>
          )}
          {paginasVisitadas.has("pagamentos") && (
            <section
              className="pagina-persistente"
              hidden={paginaAtual !== "pagamentos"}
            >
              <TelaConfiguracoesPagamento />
            </section>
          )}
          {paginasVisitadas.has("usuarios") && (
            <section
              className="pagina-persistente"
              hidden={paginaAtual !== "usuarios"}
            >
              <TelaUsuarios />
            </section>
          )}
          {paginasVisitadas.has("caixas-ativos") && (
            <section
              className="pagina-persistente"
              hidden={paginaAtual !== "caixas-ativos"}
            >
              <TelaCaixasAtivos />
            </section>
          )}
          {paginasVisitadas.has("trocas") && (
            <section
              className="pagina-persistente"
              hidden={paginaAtual !== "trocas"}
            >
              <TelaTrocasDevolucoes aoAlterar={carregarDadosIniciais} />
            </section>
          )}
          {paginasVisitadas.has("relatorios") && (
            <section
              className="pagina-persistente"
              hidden={paginaAtual !== "relatorios"}
            >
              <TelaRelatoriosAvancados />
            </section>
          )}
          {paginasVisitadas.has("backup") && (
            <section
              className="pagina-persistente"
              hidden={paginaAtual !== "backup"}
            >
              <TelaBackupSeguranca />
            </section>
          )}

          <section
            className="pagina-persistente"
            hidden={paginaAtual !== "dashboard"}
          >
            <main className="conteudo-dashboard">
          <div className="boas-vindas">
            <span>VISÃO GERAL</span>
            <h1>Olá, {dados.nome_usuario}.</h1>
            <p>
              Acompanhe o desempenho da empresa <strong>{dados.nome_empresa}</strong>.
            </p>
          </div>

          {podeVerAlertasEstoque && dados.produtos_estoque_baixo > 0 && (
            <button
              className="alerta-dashboard"
              onClick={() => navegarPara("estoque")}
            >
              <TriangleAlert size={23} />
              <div>
                <strong>
                  {dados.produtos_estoque_baixo} produto(s) precisam de reposição
                </strong>
                <span>
                  Faltam {dados.unidades_para_repor} unidade(s) para atingir o
                  estoque mínimo.
                </span>
              </div>
              <b>Ver estoque</b>
            </button>
          )}

          <div className="grade-indicadores">
            <CartaoIndicador
              titulo="Faturamento hoje"
              valor={formatoMoeda.format(dados.faturamento_diario)}
              descricao="Vendas do dia"
              icone={CircleDollarSign}
              cor="verde"
            />
            <CartaoIndicador
              titulo="Faturamento semanal"
              valor={formatoMoeda.format(dados.faturamento_semanal)}
              descricao="Desde segunda-feira"
              icone={CalendarDays}
              cor="azul"
            />
            <CartaoIndicador
              titulo="Faturamento mensal"
              valor={formatoMoeda.format(dados.faturamento_mensal)}
              descricao={`${dados.quantidade_vendas} venda(s)`}
              icone={ReceiptText}
              cor="roxo"
            />
            <CartaoIndicador
              titulo="Lucro mensal"
              valor={formatoMoeda.format(dados.lucro_mensal)}
              descricao={`Margem bruta de ${dados.margem_bruta}%`}
              icone={TrendingUp}
              cor="laranja"
            />
          </div>

          <section className="grade-dashboard-inteligente">
            <article className="painel-grafico">
              <div className="titulo-painel-dashboard">
                <div><span>ÚLTIMOS 7 DIAS</span><h2>Evolução do faturamento</h2></div>
                <strong>{formatoMoeda.format(dados.faturamento_semanal)}</strong>
              </div>
              <div className="grafico-barras">
                {dados.faturamento_ultimos_dias.map((dia) => {
                  const maior = Math.max(
                    ...dados.faturamento_ultimos_dias.map((item) => item.valor),
                    1,
                  );
                  return (
                    <div key={dia.data}>
                      <span>{formatoMoeda.format(dia.valor)}</span>
                      <i style={{ height: `${Math.max((dia.valor / maior) * 100, 4)}%` }} />
                      <b>{dia.data}</b>
                    </div>
                  );
                })}
              </div>
            </article>

            <article className="painel-mais-vendidos">
              <div className="titulo-painel-dashboard"><div><span>DESTAQUES DO MÊS</span><h2>Produtos mais vendidos</h2></div></div>
              {dados.produtos_mais_vendidos.length === 0 ? (
                <p className="estado-financeiro">As vendas aparecerão aqui.</p>
              ) : dados.produtos_mais_vendidos.map((produto, indice) => (
                <div className="item-mais-vendido" key={produto.codigo_barras}>
                  <b>{indice + 1}</b>
                  <div><strong>{produto.nome}</strong><span>{produto.quantidade} unidade(s)</span></div>
                  <strong>{formatoMoeda.format(produto.faturamento)}</strong>
                </div>
              ))}
            </article>
          </section>

          <section className="indicadores-secundarios">
            <div><Users size={18} /><span>Ticket médio</span><strong>{formatoMoeda.format(dados.ticket_medio)}</strong></div>
            <div><Package size={18} /><span>Produtos ativos</span><strong>{dados.total_produtos}</strong></div>
            <div><ReceiptText size={18} /><span>Vendas no mês</span><strong>{dados.quantidade_vendas}</strong></div>
            <button onClick={() => navegarPara("financeiro")}><TrendingUp size={18} /><span>Ver análise completa</span><strong>Financeiro →</strong></button>
          </section>

          <section className="painel-comercial-dashboard">
            <div className="titulo-painel-dashboard">
              <div><span>OPERAÇÃO COMERCIAL</span><h2>Compras, clientes e propostas</h2></div>
            </div>
            <div className="grade-indicadores-comerciais">
              <button onClick={() => navegarPara("compras")}><PackageCheck /><span>Próximos da reposição</span><strong>{dados.produtos_proximos_reposicao}</strong></button>
              <button onClick={() => navegarPara("compras")}><ShoppingCart /><span>Pedidos pendentes</span><strong>{dados.pedidos_compra_pendentes}</strong></button>
              <button onClick={() => navegarPara("clientes")}><ContactRound /><span>Clientes ativos</span><strong>{dados.total_clientes}</strong></button>
              <button onClick={() => navegarPara("orcamentos")}><ClipboardList /><span>Orçamentos pendentes</span><strong>{dados.orcamentos_pendentes}</strong></button>
              <button onClick={() => navegarPara("orcamentos")}><TrendingUp /><span>Conversão de propostas</span><strong>{dados.taxa_conversao_orcamentos}%</strong></button>
            </div>
            <div className="clientes-destaque-dashboard">
              <h3>Clientes que mais compram</h3>
              {dados.clientes_mais_compram.map((cliente, indice) => (
                <div key={cliente.cliente_id}>
                  <b>{indice + 1}</b>
                  <span>{cliente.nome}<small>{cliente.quantidade_compras} compra(s)</small></span>
                  <strong>{formatoMoeda.format(cliente.total_gasto)}</strong>
                </div>
              ))}
              {!dados.clientes_mais_compram.length && <p className="estado-financeiro">Vincule clientes às vendas para gerar este ranking.</p>}
            </div>
          </section>
            </main>
          </section>
          </Suspense>
        </div>
      </div>

      {menuAberto && (
        <button
          className="fundo-menu-celular"
          onClick={() => definirMenuAberto(false)}
          aria-label="Fechar menu"
        />
      )}
    </div>
  );
}
