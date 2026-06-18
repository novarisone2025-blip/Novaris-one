import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Clock3,
  ReceiptText,
  RefreshCw,
  RotateCcw,
  Search,
  ShoppingBag,
  UserRound,
} from "lucide-react";

import {
  baixarComprovanteVenda,
  cancelarVenda,
  confirmarPagamentoVenda,
  listarVendasRecentes,
} from "../servicos/servicoApi";
import { usarAutenticacao } from "../contexts/ContextoAutenticacao";


const formatoMoeda = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

const nomesPagamento = {
  dinheiro: "Dinheiro",
  pix: "Pix",
  debito: "Cartão de débito",
  credito: "Cartão de crédito",
};


export function TelaVendasRecentes({ aoAlterar }) {
  const { possuiPermissao } = usarAutenticacao();
  const [vendas, definirVendas] = useState([]);
  const [busca, definirBusca] = useState("");
  const [status, definirStatus] = useState("");
  const [carregando, definirCarregando] = useState(true);
  const [processando, definirProcessando] = useState(false);
  const [mensagemErro, definirMensagemErro] = useState("");
  const [vendaParaCancelar, definirVendaParaCancelar] = useState(null);
  const [motivoCancelamento, definirMotivoCancelamento] = useState("");
  const podeCancelar = possuiPermissao("vendas_cancelar");

  useEffect(() => {
    carregarVendas();
    const intervalo = window.setInterval(
      () => carregarVendas(false),
      10000,
    );
    return () => window.clearInterval(intervalo);
  }, []);

  async function carregarVendas(exibirCarregamento = true) {
    if (exibirCarregamento) definirCarregando(true);
    definirMensagemErro("");
    try {
      definirVendas(await listarVendasRecentes());
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      if (exibirCarregamento) definirCarregando(false);
    }
  }

  const vendasFiltradas = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    return vendas.filter((venda) => {
      const correspondeStatus = !status || venda.status === status;
      const correspondeBusca = !termo || [
        String(venda.id),
        venda.nome_usuario,
        venda.cargo_usuario,
        venda.nome_cliente,
        venda.forma_pagamento,
      ].some((valor) => String(valor || "").toLowerCase().includes(termo));
      return correspondeStatus && correspondeBusca;
    });
  }, [busca, status, vendas]);

  const totais = useMemo(() => ({
    quantidade: vendasFiltradas.length,
    pagas: vendasFiltradas.filter((venda) => venda.status === "pago").length,
    pendentes: vendasFiltradas.filter(
      (venda) => venda.status === "aguardando_pagamento",
    ).length,
    faturamento: vendasFiltradas
      .filter((venda) => venda.status === "pago")
      .reduce((total, venda) => total + Number(venda.valor_total), 0),
  }), [vendasFiltradas]);

  async function confirmarPagamento(vendaId) {
    definirProcessando(true);
    definirMensagemErro("");
    try {
      await confirmarPagamentoVenda(vendaId);
      await carregarVendas();
      aoAlterar?.();
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirProcessando(false);
    }
  }

  function abrirCancelamento(venda) {
    definirVendaParaCancelar(venda);
    definirMotivoCancelamento("");
    definirMensagemErro("");
  }

  async function concluirCancelamento(evento) {
    evento.preventDefault();
    definirProcessando(true);
    definirMensagemErro("");
    try {
      await cancelarVenda(vendaParaCancelar.id, motivoCancelamento);
      definirVendaParaCancelar(null);
      definirMotivoCancelamento("");
      await carregarVendas();
      aoAlterar?.();
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirProcessando(false);
    }
  }

  return (
    <main className="conteudo-dashboard conteudo-vendas-recentes">
      <div className="cabecalho-pagina">
        <div>
          <span>HISTÓRICO DO PDV</span>
          <h1>Vendas recentes</h1>
          <p>Consulte vendas, clientes, pagamentos e comprovantes separadamente do caixa.</p>
        </div>
        <button className="botao-atualizar-vendas" onClick={carregarVendas}>
          <RefreshCw size={16} /> Atualizar
        </button>
      </div>

      <section className="resumo-vendas-recentes">
        <article><ShoppingBag size={20} /><div><span>Vendas exibidas</span><strong>{totais.quantidade}</strong></div></article>
        <article><CheckCircle2 size={20} /><div><span>Vendas pagas</span><strong>{totais.pagas}</strong></div></article>
        <article><Clock3 size={20} /><div><span>Aguardando pagamento</span><strong>{totais.pendentes}</strong></div></article>
        <article><ReceiptText size={20} /><div><span>Total pago</span><strong>{formatoMoeda.format(totais.faturamento)}</strong></div></article>
      </section>

      <section className="filtros-vendas-recentes">
        <label className="campo-busca busca-vendas-recentes">
          <Search size={16} />
          <input
            value={busca}
            onChange={(evento) => definirBusca(evento.target.value)}
            placeholder="Venda, cliente, operador ou pagamento"
          />
        </label>
        <select value={status} onChange={(evento) => definirStatus(evento.target.value)}>
          <option value="">Todos os status</option>
          <option value="pago">Pago</option>
          <option value="aguardando_pagamento">Aguardando pagamento</option>
          <option value="cancelado">Cancelado</option>
        </select>
      </section>

      {mensagemErro && <p className="mensagem-erro">{mensagemErro}</p>}

      <section className="relatorio-financeiro-vendas painel-vendas-recentes">
        <div className="titulo-carrinho">
          <div><ReceiptText size={19} /><h2>Histórico de vendas</h2></div>
          <span>{vendasFiltradas.length} registro(s)</span>
        </div>
        {carregando ? (
          <p className="estado-financeiro">Carregando vendas...</p>
        ) : vendasFiltradas.length === 0 ? (
          <p className="estado-financeiro">Nenhuma venda encontrada.</p>
        ) : (
          <div className="tabela-responsiva">
            <table className="tabela-produtos tabela-vendas-financeiro tabela-vendas-separada">
              <thead>
                <tr>
                  <th>Venda</th>
                  <th>Cliente</th>
                  <th>Operador</th>
                  <th>Data</th>
                  <th>Itens</th>
                  <th>Pagamento</th>
                  <th>Status</th>
                  <th>Total</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {vendasFiltradas.map((venda) => (
                  <tr key={venda.id}>
                    <td><strong>#{venda.id}</strong></td>
                    <td>
                      <div className="cliente-venda-recente">
                        <UserRound size={15} />
                        <span>{venda.nome_cliente || "Consumidor não identificado"}</span>
                      </div>
                    </td>
                    <td>
                      <strong>{venda.nome_usuario}</strong>
                      <small>
                        {venda.cargo_usuario}
                        {venda.caixa_id ? ` · Caixa #${venda.caixa_id}` : ""}
                      </small>
                    </td>
                    <td>{new Date(venda.data_venda).toLocaleString("pt-BR")}</td>
                    <td>{venda.quantidade_itens}</td>
                    <td>
                      {nomesPagamento[venda.forma_pagamento] || venda.forma_pagamento}
                      {venda.forma_pagamento === "dinheiro" && (
                        <small className="detalhe-pagamento-dinheiro">
                          Recebido: {formatoMoeda.format(venda.valor_recebido)}
                          <br />
                          Troco: {formatoMoeda.format(venda.troco_entregue)}
                        </small>
                      )}
                    </td>
                    <td>
                      <span className={`status-venda ${venda.status}`}>
                        {venda.status === "pago"
                          ? "Pago"
                          : venda.status === "cancelado"
                            ? "Cancelada"
                            : "Aguardando pagamento"}
                      </span>
                      {venda.status === "cancelado" && (
                        <small className="detalhe-cancelamento">
                          {venda.motivo_cancelamento}
                          <br />
                          {venda.nome_usuario_cancelamento} ·{" "}
                          {new Date(venda.data_cancelamento).toLocaleString("pt-BR")}
                        </small>
                      )}
                    </td>
                    <td><strong>{formatoMoeda.format(venda.valor_total)}</strong></td>
                    <td>
                      <div className="acoes-venda-recente">
                        {venda.status === "aguardando_pagamento" ? (
                          <button
                            disabled={processando}
                            onClick={() => confirmarPagamento(venda.id)}
                          >
                            <CheckCircle2 size={14} /> Marcar pago
                          </button>
                        ) : (
                          <button onClick={() => baixarComprovanteVenda(venda.id)}>
                            <ReceiptText size={14} /> PDF
                          </button>
                        )}
                        {podeCancelar && venda.status === "pago" && (
                          <button
                            className="botao-cancelar-venda"
                            onClick={() => abrirCancelamento(venda)}
                          >
                            <RotateCcw size={14} /> Cancelar
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {vendaParaCancelar && (
        <div className="fundo-modal">
          <form className="modal-cancelamento-venda" onSubmit={concluirCancelamento}>
            <RotateCcw size={38} />
            <span>CANCELAMENTO E ESTORNO</span>
            <h2>Cancelar venda #{vendaParaCancelar.id}</h2>
            <p>
              Os {vendaParaCancelar.quantidade_itens} item(ns) serão devolvidos
              ao estoque e o valor será retirado dos indicadores financeiros.
            </p>
            <div className="resumo-cancelamento-venda">
              <span>Valor da venda</span>
              <strong>{formatoMoeda.format(vendaParaCancelar.valor_total)}</strong>
            </div>
            <label>
              <span>Motivo do cancelamento</span>
              <textarea
                minLength="5"
                maxLength="500"
                value={motivoCancelamento}
                onChange={(evento) => definirMotivoCancelamento(evento.target.value)}
                placeholder="Ex.: Cliente desistiu da compra"
                required
                autoFocus
              />
            </label>
            {mensagemErro && <p className="mensagem-erro">{mensagemErro}</p>}
            <button className="botao-confirmar-cancelamento" disabled={processando}>
              <RotateCcw size={16} />
              {processando ? "Cancelando..." : "Confirmar cancelamento"}
            </button>
            <button
              type="button"
              className="botao-fechar-pix"
              onClick={() => definirVendaParaCancelar(null)}
            >
              Voltar sem cancelar
            </button>
          </form>
        </div>
      )}
    </main>
  );
}
