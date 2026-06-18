import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeftRight,
  PackagePlus,
  RotateCcw,
  Search,
  ShoppingBag,
} from "lucide-react";

import {
  buscarProdutoVenda,
  detalharVendaParaDevolucao,
  listarTrocasDevolucoes,
  listarVendasFinanceiro,
  registrarTrocaDevolucao,
} from "../servicos/servicoApi";


const moeda = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});


export function TelaTrocasDevolucoes({ aoAlterar }) {
  const [vendas, definirVendas] = useState([]);
  const [operacoes, definirOperacoes] = useState([]);
  const [venda, definirVenda] = useState(null);
  const [tipo, definirTipo] = useState("devolucao");
  const [motivo, definirMotivo] = useState("");
  const [quantidades, definirQuantidades] = useState({});
  const [codigoNovo, definirCodigoNovo] = useState("");
  const [itensNovos, definirItensNovos] = useState([]);
  const [formaPagamento, definirFormaPagamento] = useState("dinheiro");
  const [erro, definirErro] = useState("");
  const [mensagem, definirMensagem] = useState("");
  const [salvando, definirSalvando] = useState(false);

  useEffect(() => {
    carregar();
  }, []);

  async function carregar() {
    try {
      const [dadosVendas, dadosOperacoes] = await Promise.all([
        listarVendasFinanceiro(),
        listarTrocasDevolucoes(),
      ]);
      definirVendas(dadosVendas.filter((item) => item.status === "pago"));
      definirOperacoes(dadosOperacoes);
    } catch (falha) {
      definirErro(falha.message);
    }
  }

  async function selecionarVenda(id) {
    definirErro("");
    try {
      const detalhe = await detalharVendaParaDevolucao(id);
      definirVenda(detalhe);
      definirFormaPagamento(detalhe.forma_pagamento);
      definirQuantidades({});
      definirItensNovos([]);
      definirMotivo("");
    } catch (falha) {
      definirErro(falha.message);
    }
  }

  async function adicionarProdutoNovo(evento) {
    evento.preventDefault();
    try {
      const produto = await buscarProdutoVenda(codigoNovo);
      definirItensNovos((atuais) => {
        const existe = atuais.find((item) => item.codigo_barras === produto.codigo_barras);
        if (existe) {
          return atuais.map((item) => (
            item.codigo_barras === produto.codigo_barras
              ? { ...item, quantidade: item.quantidade + 1 }
              : item
          ));
        }
        return [...atuais, { ...produto, quantidade: 1 }];
      });
      definirCodigoNovo("");
    } catch (falha) {
      definirErro(falha.message);
    }
  }

  const creditoEstimado = useMemo(() => {
    if (!venda) return 0;
    return venda.itens.reduce(
      (total, item) => (
        total + Number(item.valor_unitario) * Number(quantidades[item.id] || 0)
      ),
      0,
    );
  }, [venda, quantidades]);

  async function concluir(evento) {
    evento.preventDefault();
    const itensDevolvidos = Object.entries(quantidades)
      .filter(([, quantidade]) => Number(quantidade) > 0)
      .map(([itemId, quantidade]) => ({
        item_venda_id: Number(itemId),
        quantidade: Number(quantidade),
      }));
    if (!itensDevolvidos.length) {
      definirErro("Informe a quantidade de pelo menos um produto.");
      return;
    }
    definirSalvando(true);
    definirErro("");
    definirMensagem("");
    try {
      await registrarTrocaDevolucao(venda.id, {
        tipo,
        motivo,
        itens_devolvidos: itensDevolvidos,
        itens_novos: tipo === "troca"
          ? itensNovos.map((item) => ({
              codigo_barras: item.codigo_barras,
              quantidade: item.quantidade,
            }))
          : [],
        forma_pagamento: formaPagamento,
      });
      definirMensagem(
        tipo === "troca"
          ? "Troca registrada com sucesso."
          : "Devolucao registrada com sucesso.",
      );
      definirVenda(null);
      await carregar();
      aoAlterar();
    } catch (falha) {
      definirErro(falha.message);
    } finally {
      definirSalvando(false);
    }
  }

  return (
    <main className="conteudo-dashboard conteudo-operacoes-venda">
      <div className="cabecalho-pagina">
        <div>
          <span>POS-VENDA</span>
          <h1>Trocas e devolucoes</h1>
          <p>Retorne produtos ao estoque e mantenha financeiro e auditoria sincronizados.</p>
        </div>
      </div>

      {erro && <p className="mensagem-erro">{erro}</p>}
      {mensagem && <p className="mensagem-sucesso">{mensagem}</p>}

      <section className="grade-operacoes-venda">
        <section className="lista-estoque">
          <div className="barra-lista">
            <div><h2>Vendas finalizadas</h2><small>Selecione uma venda para continuar</small></div>
          </div>
          <div className="lista-vendas-devolucao">
            {vendas.map((item) => (
              <button
                key={item.id}
                className={venda?.id === item.id ? "ativo" : ""}
                onClick={() => selecionarVenda(item.id)}
              >
                <ShoppingBag size={18} />
                <div>
                  <strong>Venda #{item.id}</strong>
                  <span>{item.nome_usuario} · {new Date(item.data_venda).toLocaleString("pt-BR")}</span>
                </div>
                <b>{moeda.format(item.valor_total)}</b>
              </button>
            ))}
          </div>
        </section>

        <form className="painel-operacao-venda" onSubmit={concluir}>
          {!venda ? (
            <div className="estado-vazio">
              <RotateCcw size={35} />
              <h3>Selecione uma venda</h3>
              <p>Os itens disponiveis para troca ou devolucao aparecerao aqui.</p>
            </div>
          ) : (
            <>
              <div className="tipo-operacao-venda">
                <button type="button" className={tipo === "devolucao" ? "ativo" : ""} onClick={() => definirTipo("devolucao")}><RotateCcw size={16} /> Devolucao</button>
                <button type="button" className={tipo === "troca" ? "ativo" : ""} onClick={() => definirTipo("troca")}><ArrowLeftRight size={16} /> Troca</button>
              </div>
              <h2>Venda #{venda.id}</h2>
              <div className="itens-devolucao">
                {venda.itens.map((item) => (
                  <label key={item.id}>
                    <div>
                      <strong>{item.nome_produto}</strong>
                      <span>{item.codigo_barras} · {moeda.format(item.valor_unitario)}</span>
                      <small>Disponivel para devolucao: {item.quantidade_disponivel_devolucao}</small>
                    </div>
                    <input
                      type="number"
                      min="0"
                      max={item.quantidade_disponivel_devolucao}
                      value={quantidades[item.id] || ""}
                      onChange={(evento) => definirQuantidades({
                        ...quantidades,
                        [item.id]: evento.target.value,
                      })}
                      placeholder="0"
                    />
                  </label>
                ))}
              </div>

              {tipo === "troca" && (
                <div className="novos-itens-troca">
                  <div className="busca-item-troca">
                    <Search size={17} />
                    <input value={codigoNovo} onChange={(e) => definirCodigoNovo(e.target.value)} placeholder="Codigo de barras do novo produto" />
                    <button type="button" onClick={adicionarProdutoNovo}><PackagePlus size={15} /> Adicionar</button>
                  </div>
                  {itensNovos.map((item) => (
                    <article key={item.id}>
                      <div><strong>{item.nome}</strong><span>{item.codigo_barras}</span></div>
                      <input type="number" min="1" max={item.quantidade} value={item.quantidade} onChange={(e) => definirItensNovos((atuais) => atuais.map((atual) => atual.id === item.id ? {...atual, quantidade: Number(e.target.value)} : atual))} />
                      <b>{moeda.format(Number(item.preco) * item.quantidade)}</b>
                    </article>
                  ))}
                </div>
              )}

              <div className="resumo-operacao-venda">
                <span>Credito estimado</span>
                <strong>{moeda.format(creditoEstimado)}</strong>
              </div>
              <label className="campo-formulario"><span>Forma de estorno ou diferenca</span><div><select value={formaPagamento} onChange={(e) => definirFormaPagamento(e.target.value)}><option value="dinheiro">Dinheiro</option><option value="pix">PIX</option><option value="debito">Debito</option><option value="credito">Credito</option></select></div></label>
              <label className="campo-formulario"><span>Motivo obrigatorio</span><div><textarea minLength="5" maxLength="500" value={motivo} onChange={(e) => definirMotivo(e.target.value)} required /></div></label>
              <button className="botao-principal" disabled={salvando}>{salvando ? "Registrando..." : `Confirmar ${tipo}`}</button>
            </>
          )}
        </form>
      </section>

      <section className="lista-estoque historico-operacoes-venda">
        <div className="barra-lista"><div><h2>Historico de operacoes</h2><small>{operacoes.length} registro(s)</small></div></div>
        <div className="lista-fluxo">
          {operacoes.map((item) => (
            <article key={item.id}>
              <div className="icone-fluxo saida"><RotateCcw size={18} /></div>
              <div><strong>{item.tipo} da venda #{item.venda_id}</strong><span>{item.motivo} · {new Date(item.data_operacao).toLocaleString("pt-BR")}</span><small>{item.nome_usuario} · Caixa #{item.caixa_id}</small></div>
              <b>{item.valor_estornado > 0 ? `-${moeda.format(item.valor_estornado)}` : `+${moeda.format(item.valor_adicional)}`}</b>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
