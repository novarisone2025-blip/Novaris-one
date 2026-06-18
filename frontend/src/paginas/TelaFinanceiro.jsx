import { useEffect, useState } from "react";
import {
  ArrowDownCircle,
  ArrowUpCircle,
  FileSpreadsheet,
  FileText,
  Landmark,
  Plus,
  TrendingUp,
  WalletCards,
} from "lucide-react";

import {
  baixarRelatorioFinanceiro,
  buscarResumoFinanceiro,
  listarFluxoCaixa,
  registrarLancamentoFinanceiro,
} from "../servicos/servicoApi";


const formatoMoeda = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});


export function TelaFinanceiro({ aoAlterarFinanceiro }) {
  const hoje = new Date().toISOString().slice(0, 10);
  const primeiroDia = `${hoje.slice(0, 8)}01`;
  const [filtros, definirFiltros] = useState({
    data_inicial: primeiroDia,
    data_final: hoje,
  });
  const [resumo, definirResumo] = useState(null);
  const [fluxo, definirFluxo] = useState([]);
  const [formulario, definirFormulario] = useState({
    tipo: "saida",
    categoria: "",
    descricao: "",
    valor: "",
  });
  const [mensagemErro, definirMensagemErro] = useState("");

  useEffect(() => {
    carregarFinanceiro();
  }, []);

  async function carregarFinanceiro(novosFiltros = filtros) {
    try {
      const [dadosResumo, dadosFluxo] = await Promise.all([
        buscarResumoFinanceiro(novosFiltros),
        listarFluxoCaixa(novosFiltros),
      ]);
      definirResumo(dadosResumo);
      definirFluxo(dadosFluxo);
    } catch (erro) {
      definirMensagemErro(erro.message);
    }
  }

  async function salvarLancamento(evento) {
    evento.preventDefault();
    definirMensagemErro("");
    try {
      await registrarLancamentoFinanceiro({
        ...formulario,
        valor: Number(formulario.valor),
      });
      definirFormulario({
        tipo: "saida",
        categoria: "",
        descricao: "",
        valor: "",
      });
      await carregarFinanceiro();
      aoAlterarFinanceiro();
    } catch (erro) {
      definirMensagemErro(erro.message);
    }
  }

  if (!resumo) return <main className="conteudo-dashboard"><p>Carregando financeiro...</p></main>;

  return (
    <main className="conteudo-dashboard conteudo-financeiro">
      <div className="cabecalho-pagina">
        <div><span>GESTÃO FINANCEIRA</span><h1>Financeiro</h1><p>Acompanhe receitas, despesas, lucro e fluxo de caixa.</p></div>
        <div className="acoes-relatorio">
          <button onClick={() => baixarRelatorioFinanceiro("pdf", filtros)}><FileText size={16} /> PDF</button>
          <button onClick={() => baixarRelatorioFinanceiro("excel", filtros)}><FileSpreadsheet size={16} /> Excel</button>
        </div>
      </div>

      <div className="filtros-financeiro">
        <label><span>De</span><input type="date" value={filtros.data_inicial} onChange={(evento) => definirFiltros({...filtros, data_inicial: evento.target.value})} /></label>
        <label><span>Até</span><input type="date" value={filtros.data_final} onChange={(evento) => definirFiltros({...filtros, data_final: evento.target.value})} /></label>
        <button onClick={() => carregarFinanceiro()}>Atualizar período</button>
      </div>

      <section className="grade-indicadores financeiros">
        <article className="cartao-indicador"><div className="icone-indicador verde"><TrendingUp size={20} /></div><div><span>Faturamento</span><strong>{formatoMoeda.format(resumo.faturamento)}</strong><small>{resumo.quantidade_vendas} venda(s)</small></div></article>
        <article className="cartao-indicador"><div className="icone-indicador azul"><WalletCards size={20} /></div><div><span>Lucro bruto</span><strong>{formatoMoeda.format(resumo.lucro_bruto)}</strong><small>Margem de {resumo.margem_bruta}%</small></div></article>
        <article className="cartao-indicador"><div className="icone-indicador laranja"><ArrowDownCircle size={20} /></div><div><span>Despesas</span><strong>{formatoMoeda.format(resumo.despesas)}</strong><small>Lançamentos de saída</small></div></article>
        <article className="cartao-indicador"><div className="icone-indicador roxo"><Landmark size={20} /></div><div><span>Saldo de caixa</span><strong>{formatoMoeda.format(resumo.saldo_caixa)}</strong><small>Entradas menos saídas</small></div></article>
      </section>

      <section className="grade-financeiro">
        <form className="formulario-produto formulario-financeiro" onSubmit={salvarLancamento}>
          <div className="titulo-formulario-produto"><div><span>NOVO LANÇAMENTO</span><h2>Entrada ou despesa</h2></div></div>
          <label className="campo-formulario"><span>Tipo</span><div><select value={formulario.tipo} onChange={(evento) => definirFormulario({...formulario, tipo: evento.target.value})}><option value="entrada">Entrada</option><option value="saida">Saída</option></select></div></label>
          <label className="campo-formulario"><span>Categoria</span><div><input value={formulario.categoria} onChange={(evento) => definirFormulario({...formulario, categoria: evento.target.value})} placeholder="Ex.: Aluguel" required /></div></label>
          <label className="campo-formulario"><span>Descrição</span><div><input value={formulario.descricao} onChange={(evento) => definirFormulario({...formulario, descricao: evento.target.value})} required /></div></label>
          <label className="campo-formulario"><span>Valor</span><div><span>R$</span><input type="number" min="0.01" step="0.01" value={formulario.valor} onChange={(evento) => definirFormulario({...formulario, valor: evento.target.value})} required /></div></label>
          {mensagemErro && <p className="mensagem-erro">{mensagemErro}</p>}
          <button className="botao-principal"><Plus size={16} /> Registrar lançamento</button>
        </form>

        <section className="lista-estoque fluxo-caixa">
          <div className="barra-lista"><div><h2>Fluxo de caixa</h2><small>Vendas e lançamentos manuais</small></div></div>
          <div className="lista-fluxo">
            {fluxo.map((item) => (
              <article key={item.id}>
                <div className={`icone-fluxo ${item.tipo}`}>
                  {item.tipo === "entrada" ? <ArrowUpCircle size={19} /> : <ArrowDownCircle size={19} />}
                </div>
                <div>
                  <strong>{item.descricao}</strong>
                  {item.forma_pagamento === "dinheiro" && (
                    <small className="detalhe-dinheiro-fluxo">
                      Recebido {formatoMoeda.format(item.valor_recebido)}
                      {" · "}
                      Troco {formatoMoeda.format(item.troco_entregue)}
                    </small>
                  )}
                  <span>{item.categoria} • {new Date(item.data_lancamento).toLocaleString("pt-BR")}</span>
                  <small>
                    {item.origem === "venda"
                      ? `${item.nome_usuario} · Caixa #${item.caixa_id}`
                      : `Registrado por ${item.nome_usuario}`}
                  </small>
                </div>
                <b className={item.tipo}>{item.tipo === "entrada" ? "+" : "-"} {formatoMoeda.format(item.valor)}</b>
              </article>
            ))}
            {fluxo.length === 0 && <p className="estado-financeiro">Nenhum movimento no período.</p>}
          </div>
        </section>
      </section>
    </main>
  );
}
