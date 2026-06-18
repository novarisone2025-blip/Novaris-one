import { useEffect, useState } from "react";
import {
  CheckCircle2,
  Clock3,
  PackagePlus,
  Send,
  ShoppingBag,
  Truck,
  XCircle,
} from "lucide-react";

import {
  alterarStatusPedidoCompra,
  criarPedidoCompra,
  listarPedidosCompra,
  listarSugestoesReposicao,
} from "../servicos/servicoApi";


const formatoMoeda = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});


export function TelaCompras({ aoAlterar }) {
  const [sugestoes, definirSugestoes] = useState([]);
  const [pedidos, definirPedidos] = useState([]);
  const [mensagemErro, definirMensagemErro] = useState("");
  const [processando, definirProcessando] = useState(null);

  useEffect(() => {
    carregar();
  }, []);

  async function carregar() {
    try {
      const [novasSugestoes, novosPedidos] = await Promise.all([
        listarSugestoesReposicao(),
        listarPedidosCompra(),
      ]);
      definirSugestoes(novasSugestoes);
      definirPedidos(novosPedidos);
    } catch (erro) {
      definirMensagemErro(erro.message);
    }
  }

  async function gerarPedido(sugestao) {
    if (!sugestao.fornecedor_id) {
      definirMensagemErro("Vincule um fornecedor ao produto antes de gerar o pedido.");
      return;
    }
    definirProcessando(`novo-${sugestao.produto_id}`);
    definirMensagemErro("");
    try {
      await criarPedidoCompra({
        fornecedor_id: sugestao.fornecedor_id,
        itens: [{
          produto_id: sugestao.produto_id,
          quantidade: sugestao.quantidade_sugerida,
          custo_unitario: Number(sugestao.custo_unitario),
        }],
        observacoes: "Pedido gerado pela sugestão automática de reposição.",
      });
      await carregar();
      aoAlterar?.();
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirProcessando(null);
    }
  }

  async function mudarStatus(pedido, status) {
    definirProcessando(`${pedido.id}-${status}`);
    definirMensagemErro("");
    try {
      await alterarStatusPedidoCompra(pedido.id, status);
      await carregar();
      aoAlterar?.();
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirProcessando(null);
    }
  }

  return (
    <main className="conteudo-dashboard conteudo-comercial">
      <div className="cabecalho-pagina">
        <div>
          <span>ABASTECIMENTO INTELIGENTE</span>
          <h1>Compras e reposição</h1>
          <p>Transforme alertas de estoque em pedidos rastreáveis.</p>
        </div>
      </div>

      {mensagemErro && <p className="mensagem-erro">{mensagemErro}</p>}

      <section className="resumo-comercial">
        <article><PackagePlus /><div><span>Sugestões ativas</span><strong>{sugestoes.length}</strong></div></article>
        <article><Clock3 /><div><span>Pedidos pendentes</span><strong>{pedidos.filter((item) => ["pendente", "enviado"].includes(item.status)).length}</strong></div></article>
        <article><ShoppingBag /><div><span>Total em pedidos</span><strong>{formatoMoeda.format(pedidos.reduce((total, item) => total + Number(item.valor_total), 0))}</strong></div></article>
      </section>

      <section className="lista-estoque bloco-comercial">
        <div className="barra-lista">
          <div><h2>Sugestões automáticas</h2><small>Produtos no estoque mínimo ou abaixo dele</small></div>
        </div>
        {sugestoes.length === 0 ? (
          <div className="estado-vazio"><CheckCircle2 /><h3>Estoque equilibrado</h3><p>Nenhuma reposição é necessária agora.</p></div>
        ) : (
          <div className="grade-sugestoes-compra">
            {sugestoes.map((item) => (
              <article key={item.produto_id}>
                <div className="icone-comercial"><PackagePlus size={20} /></div>
                <div>
                  <h3>{item.nome_produto}</h3>
                  <span>{item.codigo_barras} · {item.nome_fornecedor}</span>
                  <small>Atual: {item.estoque_atual} · Mínimo: {item.estoque_minimo}</small>
                </div>
                <div className="quantidade-sugerida">
                  <span>Comprar</span>
                  <strong>{item.quantidade_sugerida} un.</strong>
                  <small>{formatoMoeda.format(item.custo_estimado)}</small>
                </div>
                <button
                  disabled={processando || !item.fornecedor_id}
                  onClick={() => gerarPedido(item)}
                >
                  <ShoppingBag size={15} /> Gerar pedido
                </button>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="lista-estoque bloco-comercial">
        <div className="barra-lista">
          <div><h2>Pedidos de compra</h2><small>Histórico e acompanhamento de recebimento</small></div>
        </div>
        <div className="tabela-responsiva">
          <table className="tabela-produtos tabela-comercial">
            <thead><tr><th>Pedido</th><th>Fornecedor</th><th>Itens</th><th>Total</th><th>Status</th><th>Ações</th></tr></thead>
            <tbody>
              {pedidos.map((pedido) => (
                <tr key={pedido.id}>
                  <td><strong>#{pedido.id}</strong><small>{new Date(pedido.data_criacao).toLocaleString("pt-BR")}</small></td>
                  <td>{pedido.nome_fornecedor}</td>
                  <td>{pedido.itens.map((item) => `${item.quantidade}x ${item.nome_produto}`).join(", ")}</td>
                  <td><strong>{formatoMoeda.format(pedido.valor_total)}</strong></td>
                  <td><span className={`status-comercial ${pedido.status}`}>{pedido.status}</span></td>
                  <td>
                    <div className="acoes-comerciais">
                      {pedido.status === "pendente" && <button onClick={() => mudarStatus(pedido, "enviado")}><Send size={14} /> Enviar</button>}
                      {["pendente", "enviado"].includes(pedido.status) && <button className="receber" onClick={() => mudarStatus(pedido, "recebido")}><Truck size={14} /> Receber</button>}
                      {["pendente", "enviado"].includes(pedido.status) && <button className="cancelar" onClick={() => mudarStatus(pedido, "cancelado")}><XCircle size={14} /></button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
