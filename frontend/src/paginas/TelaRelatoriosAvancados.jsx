import { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  FileSpreadsheet,
  FileText,
  Package,
  ReceiptText,
  TrendingUp,
} from "lucide-react";

import {
  baixarRelatorioAvancado,
  buscarOpcoesRelatorioAvancado,
  buscarRelatorioAvancado,
} from "../servicos/servicoApi";


const moeda = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});


export function TelaRelatoriosAvancados() {
  const hoje = new Date().toISOString().slice(0, 10);
  const [filtros, definirFiltros] = useState({
    periodo: "mes",
    data_inicial: `${hoje.slice(0, 8)}01`,
    data_final: hoje,
    produto_id: "",
    categoria: "",
    usuario_id: "",
    caixa_id: "",
    forma_pagamento: "",
  });
  const [dados, definirDados] = useState(null);
  const [produtos, definirProdutos] = useState([]);
  const [usuarios, definirUsuarios] = useState([]);
  const [caixas, definirCaixas] = useState([]);
  const [erro, definirErro] = useState("");

  useEffect(() => {
    Promise.all([
      buscarOpcoesRelatorioAvancado(),
      buscarRelatorioAvancado(filtros),
    ]).then(([opcoes, relatorio]) => {
      definirProdutos(opcoes.produtos);
      definirUsuarios(opcoes.usuarios);
      definirCaixas(opcoes.caixas);
      definirDados(relatorio);
    }).catch((falha) => definirErro(falha.message));
  }, []);

  const categorias = useMemo(
    () => [...new Set(produtos.map((item) => item.categoria))].sort(),
    [produtos],
  );

  async function atualizar() {
    try {
      definirErro("");
      definirDados(await buscarRelatorioAvancado(filtros));
    } catch (falha) {
      definirErro(falha.message);
    }
  }

  return (
    <main className="conteudo-dashboard conteudo-relatorios">
      <div className="cabecalho-pagina">
        <div><span>ANALISE COMERCIAL</span><h1>Relatorios avancados</h1><p>Filtre vendas, lucro e produtos por todos os pontos da operacao.</p></div>
        <div className="acoes-relatorio">
          <button onClick={() => baixarRelatorioAvancado("pdf", filtros)}><FileText size={16} /> PDF</button>
          <button onClick={() => baixarRelatorioAvancado("excel", filtros)}><FileSpreadsheet size={16} /> Excel</button>
        </div>
      </div>

      <section className="filtros-relatorio-avancado">
        <label><span>Periodo</span><select value={filtros.periodo} onChange={(e) => definirFiltros({...filtros, periodo: e.target.value})}><option value="dia">Dia</option><option value="semana">Semana</option><option value="mes">Mes</option><option value="personalizado">Personalizado</option></select></label>
        <label><span>De</span><input type="date" value={filtros.data_inicial} onChange={(e) => definirFiltros({...filtros, data_inicial: e.target.value})} /></label>
        <label><span>Ate</span><input type="date" value={filtros.data_final} onChange={(e) => definirFiltros({...filtros, data_final: e.target.value})} /></label>
        <label><span>Produto</span><select value={filtros.produto_id} onChange={(e) => definirFiltros({...filtros, produto_id: e.target.value})}><option value="">Todos</option>{produtos.map((item) => <option key={item.id} value={item.id}>{item.nome}</option>)}</select></label>
        <label><span>Categoria</span><select value={filtros.categoria} onChange={(e) => definirFiltros({...filtros, categoria: e.target.value})}><option value="">Todas</option>{categorias.map((item) => <option key={item}>{item}</option>)}</select></label>
        <label><span>Usuario</span><select value={filtros.usuario_id} onChange={(e) => definirFiltros({...filtros, usuario_id: e.target.value})}><option value="">Todos</option>{usuarios.map((item) => <option key={item.id} value={item.id}>{item.nome}</option>)}</select></label>
        <label><span>Caixa</span><select value={filtros.caixa_id} onChange={(e) => definirFiltros({...filtros, caixa_id: e.target.value})}><option value="">Todos</option>{caixas.map((item) => <option key={item.id} value={item.id}>Caixa #{item.id}</option>)}</select></label>
        <label><span>Pagamento</span><select value={filtros.forma_pagamento} onChange={(e) => definirFiltros({...filtros, forma_pagamento: e.target.value})}><option value="">Todos</option><option value="dinheiro">Dinheiro</option><option value="pix">PIX</option><option value="debito">Debito</option><option value="credito">Credito</option></select></label>
        <button onClick={atualizar}>Aplicar filtros</button>
      </section>

      {erro && <p className="mensagem-erro">{erro}</p>}
      {!dados ? <p>Carregando relatorio...</p> : (
        <>
          <section className="grade-indicadores financeiros">
            <article className="cartao-indicador"><div className="icone-indicador verde"><TrendingUp size={20} /></div><div><span>Faturamento</span><strong>{moeda.format(dados.faturamento)}</strong><small>{dados.quantidade_vendas} venda(s)</small></div></article>
            <article className="cartao-indicador"><div className="icone-indicador azul"><BarChart3 size={20} /></div><div><span>Lucro</span><strong>{moeda.format(dados.lucro)}</strong><small>Periodo selecionado</small></div></article>
            <article className="cartao-indicador"><div className="icone-indicador roxo"><Package size={20} /></div><div><span>Quantidade vendida</span><strong>{dados.quantidade_vendida}</strong><small>Liquida de devolucoes</small></div></article>
            <article className="cartao-indicador"><div className="icone-indicador laranja"><ReceiptText size={20} /></div><div><span>Ticket medio</span><strong>{moeda.format(dados.ticket_medio)}</strong><small>Por venda</small></div></article>
          </section>
          <section className="lista-estoque">
            <div className="barra-lista"><div><h2>Produtos mais vendidos</h2><small>{dados.data_inicial} a {dados.data_final}</small></div></div>
            <div className="tabela-responsiva"><table className="tabela-produtos"><thead><tr><th>Produto</th><th>Categoria</th><th>Quantidade</th><th>Faturamento</th></tr></thead><tbody>
              {dados.produtos_mais_vendidos.map((item) => <tr key={item.produto_id}><td><strong>{item.nome}</strong><small>{item.codigo_barras}</small></td><td>{item.categoria}</td><td>{item.quantidade}</td><td><strong>{moeda.format(item.faturamento)}</strong></td></tr>)}
              {!dados.produtos_mais_vendidos.length && <tr><td colSpan="4">Nenhuma venda encontrada.</td></tr>}
            </tbody></table></div>
          </section>
        </>
      )}
    </main>
  );
}
