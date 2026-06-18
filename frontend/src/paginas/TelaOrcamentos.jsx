import { useEffect, useMemo, useState } from "react";
import {
  CalendarDays,
  CheckCircle2,
  FileText,
  Mail,
  MapPin,
  MessageCircle,
  Phone,
  Plus,
  ReceiptText,
  ShoppingCart,
  Trash2,
  UserRound,
  X,
  XCircle,
} from "lucide-react";

import {
  baixarOrcamentoPdf,
  buscarLinksOrcamento,
  cancelarOrcamento,
  converterOrcamento,
  criarOrcamento,
  listarClientes,
  listarOrcamentos,
  listarProdutos,
} from "../servicos/servicoApi";


const formatoMoeda = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});

const nomesPagamento = {
  dinheiro: "Dinheiro",
  pix: "PIX",
  debito: "Cartão de débito",
  credito: "Cartão de crédito",
};


export function TelaOrcamentos({ aoAlterar }) {
  const validadeInicial = new Date(Date.now() + 7 * 86400000)
    .toISOString()
    .slice(0, 10);
  const [produtos, definirProdutos] = useState([]);
  const [clientes, definirClientes] = useState([]);
  const [orcamentos, definirOrcamentos] = useState([]);
  const [itens, definirItens] = useState([]);
  const [produtoId, definirProdutoId] = useState("");
  const [clienteId, definirClienteId] = useState("");
  const [desconto, definirDesconto] = useState("0");
  const [validade, definirValidade] = useState(validadeInicial);
  const [observacoes, definirObservacoes] = useState("");
  const [mensagemErro, definirMensagemErro] = useState("");
  const [mensagemSucesso, definirMensagemSucesso] = useState("");
  const [salvando, definirSalvando] = useState(false);
  const [orcamentoConversao, definirOrcamentoConversao] = useState(null);
  const [formaPagamento, definirFormaPagamento] = useState("dinheiro");
  const [convertendo, definirConvertendo] = useState(false);

  useEffect(() => {
    carregar();
  }, []);

  async function carregar() {
    try {
      const [novosProdutos, novosClientes, novosOrcamentos] = await Promise.all([
        listarProdutos(),
        listarClientes(),
        listarOrcamentos(),
      ]);
      definirProdutos(novosProdutos);
      definirClientes(novosClientes);
      definirOrcamentos(novosOrcamentos);
    } catch (erro) {
      definirMensagemErro(erro.message);
    }
  }

  const clienteSelecionado = useMemo(
    () => clientes.find((cliente) => cliente.id === Number(clienteId)) || null,
    [clientes, clienteId],
  );

  const subtotal = useMemo(
    () => itens.reduce(
      (total, item) => total + Number(item.preco) * Number(item.quantidade),
      0,
    ),
    [itens],
  );

  const valorTotal = Math.max(subtotal - Number(desconto || 0), 0);

  function adicionarProduto() {
    const produto = produtos.find((item) => item.id === Number(produtoId));
    if (!produto) return;
    definirItens((atuais) => {
      const existente = atuais.find((item) => item.id === produto.id);
      if (existente) {
        return atuais.map((item) => (
          item.id === produto.id
            ? { ...item, quantidade: Number(item.quantidade) + 1 }
            : item
        ));
      }
      return [...atuais, { ...produto, quantidade: 1 }];
    });
    definirProdutoId("");
    definirMensagemErro("");
  }

  function alterarQuantidade(produtoIdAlterado, quantidade) {
    const valor = Math.max(Number(quantidade) || 1, 1);
    definirItens((atuais) => atuais.map((produto) => (
      produto.id === produtoIdAlterado
        ? { ...produto, quantidade: valor }
        : produto
    )));
  }

  function removerProduto(produtoIdRemovido) {
    definirItens((atuais) => atuais.filter(
      (produto) => produto.id !== produtoIdRemovido,
    ));
  }

  async function salvar(evento) {
    evento.preventDefault();
    if (!itens.length) {
      definirMensagemErro("Adicione pelo menos um produto ao orçamento.");
      return;
    }
    if (Number(desconto || 0) > subtotal) {
      definirMensagemErro("O desconto não pode ser maior que o subtotal.");
      return;
    }
    definirSalvando(true);
    definirMensagemErro("");
    definirMensagemSucesso("");
    try {
      const criado = await criarOrcamento({
        cliente_id: clienteId ? Number(clienteId) : null,
        itens: itens.map((item) => ({
          produto_id: item.id,
          quantidade: Number(item.quantidade),
          desconto: 0,
        })),
        desconto: Number(desconto || 0),
        observacoes,
        validade,
      });
      definirItens([]);
      definirProdutoId("");
      definirClienteId("");
      definirDesconto("0");
      definirObservacoes("");
      definirValidade(validadeInicial);
      definirMensagemSucesso(
        `Orçamento #${criado.id} criado. O PDF profissional já está disponível.`,
      );
      await carregar();
      aoAlterar?.();
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function compartilhar(item, tipo) {
    definirMensagemErro("");
    definirMensagemSucesso("");
    const janelaWhatsApp = tipo === "whatsapp"
      ? window.open("about:blank", "_blank")
      : null;
    try {
      const links = await buscarLinksOrcamento(item.id);
      const endereco = tipo === "whatsapp"
        ? links.whatsapp_url
        : links.email_url;
      if (tipo === "whatsapp" && janelaWhatsApp) {
        janelaWhatsApp.opener = null;
        janelaWhatsApp.location.href = endereco;
      } else {
        window.location.href = endereco;
      }
      definirMensagemSucesso(
        tipo === "whatsapp"
          ? "Mensagem do orçamento preparada para o WhatsApp."
          : "E-mail do orçamento preparado no aplicativo padrão.",
      );
    } catch (erro) {
      janelaWhatsApp?.close();
      definirMensagemErro(erro.message);
    }
  }

  async function baixarPdf(item) {
    definirMensagemErro("");
    try {
      await baixarOrcamentoPdf(item.id);
      definirMensagemSucesso(
        `PDF do orçamento #${item.id} gerado com sucesso.`,
      );
    } catch (erro) {
      definirMensagemErro(erro.message);
    }
  }

  function abrirConversao(item) {
    definirOrcamentoConversao(item);
    definirFormaPagamento("dinheiro");
    definirMensagemErro("");
  }

  async function confirmarConversao() {
    if (!orcamentoConversao) return;
    definirConvertendo(true);
    definirMensagemErro("");
    definirMensagemSucesso("");
    try {
      const venda = await converterOrcamento(
        orcamentoConversao.id,
        formaPagamento,
      );
      definirMensagemSucesso(
        venda.status === "aguardando_pagamento"
          ? `Venda #${venda.id} criada e aguardando confirmação do PIX.`
          : `Orçamento convertido na venda #${venda.id}. Estoque e relatórios atualizados.`,
      );
      definirOrcamentoConversao(null);
      await carregar();
      aoAlterar?.();
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirConvertendo(false);
    }
  }

  async function cancelar(item) {
    if (!window.confirm(`Cancelar o orçamento #${item.id}?`)) return;
    definirMensagemErro("");
    definirMensagemSucesso("");
    try {
      await cancelarOrcamento(item.id);
      definirMensagemSucesso(`Orçamento #${item.id} cancelado.`);
      await carregar();
      aoAlterar?.();
    } catch (erro) {
      definirMensagemErro(erro.message);
    }
  }

  return (
    <main className="conteudo-dashboard conteudo-comercial">
      <div className="cabecalho-pagina">
        <div>
          <span>PROPOSTAS COMERCIAIS</span>
          <h1>Orçamentos</h1>
          <p>Monte propostas profissionais e converta em venda sem redigitar.</p>
        </div>
      </div>

      {mensagemSucesso && (
        <div className="mensagem-sucesso-orcamento">
          <CheckCircle2 size={18} />
          <span>{mensagemSucesso}</span>
          <button onClick={() => definirMensagemSucesso("")} aria-label="Fechar">
            <X size={15} />
          </button>
        </div>
      )}
      {mensagemErro && <p className="mensagem-erro">{mensagemErro}</p>}

      <section className="grade-orcamentos">
        <form
          className="formulario-produto formulario-orcamento"
          onSubmit={salvar}
        >
          <div className="titulo-formulario-produto">
            <div>
              <span>NOVO ORÇAMENTO</span>
              <h2>Montar proposta</h2>
            </div>
          </div>

          <label className="campo-formulario">
            <span>Cliente</span>
            <div>
              <UserRound size={15} />
              <select
                value={clienteId}
                onChange={(evento) => definirClienteId(evento.target.value)}
              >
                <option value="">Consumidor não identificado</option>
                {clientes.map((cliente) => (
                  <option key={cliente.id} value={cliente.id}>
                    {cliente.nome}
                  </option>
                ))}
              </select>
            </div>
          </label>

          <article className={`cliente-orcamento ${clienteSelecionado ? "selecionado" : ""}`}>
            <div className="icone-cliente-orcamento">
              <UserRound size={19} />
            </div>
            {clienteSelecionado ? (
              <div className="dados-cliente-orcamento">
                <div className="cabecalho-cliente-orcamento">
                  <div>
                    <span>CLIENTE SELECIONADO</span>
                    <strong>{clienteSelecionado.nome}</strong>
                  </div>
                  {clienteSelecionado.documento && (
                    <small>{clienteSelecionado.documento}</small>
                  )}
                </div>
                <div className="contatos-cliente-orcamento">
                  <span>
                    <Phone size={12} />
                    {clienteSelecionado.whatsapp
                      || clienteSelecionado.telefone
                      || "Telefone não informado"}
                  </span>
                  <span>
                    <Mail size={12} />
                    {clienteSelecionado.email || "E-mail não informado"}
                  </span>
                  <span>
                    <MapPin size={12} />
                    {clienteSelecionado.endereco || "Endereço não informado"}
                  </span>
                </div>
              </div>
            ) : (
              <div className="dados-cliente-orcamento vazio">
                <strong>Nenhum cliente selecionado</strong>
                <span>Selecione um cliente para incluir seus dados no PDF.</span>
              </div>
            )}
          </article>

          <div className="seletor-produto-orcamento">
            <select
              value={produtoId}
              onChange={(evento) => definirProdutoId(evento.target.value)}
            >
              <option value="">Selecione um produto</option>
              {produtos.map((produto) => (
                <option key={produto.id} value={produto.id}>
                  {produto.nome} · {formatoMoeda.format(produto.preco)}
                </option>
              ))}
            </select>
            <button type="button" onClick={adicionarProduto} disabled={!produtoId}>
              <Plus size={15} /> Adicionar produto
            </button>
          </div>

          <div className="tabela-itens-orcamento-responsiva">
            <table className="tabela-itens-orcamento">
              <thead>
                <tr>
                  <th>Produto</th>
                  <th>Quantidade</th>
                  <th>Valor unitário</th>
                  <th>Subtotal</th>
                  <th aria-label="Ações" />
                </tr>
              </thead>
              <tbody>
                {itens.length === 0 ? (
                  <tr className="linha-vazia-orcamento">
                    <td colSpan="5">
                      <ShoppingCart size={22} />
                      <span>Adicione produtos para montar a proposta.</span>
                    </td>
                  </tr>
                ) : itens.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.nome}</strong>
                      <small>{item.codigo_barras}</small>
                    </td>
                    <td>
                      <input
                        type="number"
                        min="1"
                        value={item.quantidade}
                        aria-label={`Quantidade de ${item.nome}`}
                        onChange={(evento) => alterarQuantidade(
                          item.id,
                          evento.target.value,
                        )}
                      />
                    </td>
                    <td>{formatoMoeda.format(item.preco)}</td>
                    <td>
                      <strong>
                        {formatoMoeda.format(
                          Number(item.preco) * Number(item.quantidade),
                        )}
                      </strong>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="remover-item-orcamento"
                        onClick={() => removerProduto(item.id)}
                        aria-label={`Remover ${item.nome}`}
                      >
                        <Trash2 size={15} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="duas-colunas">
            <label className="campo-formulario">
              <span>Desconto geral</span>
              <div>
                <span>R$</span>
                <input
                  type="number"
                  min="0"
                  max={subtotal}
                  step="0.01"
                  value={desconto}
                  onChange={(evento) => definirDesconto(evento.target.value)}
                />
              </div>
            </label>
            <label className="campo-formulario">
              <span>Validade</span>
              <div>
                <CalendarDays size={15} />
                <input
                  type="date"
                  value={validade}
                  min={new Date().toISOString().slice(0, 10)}
                  onChange={(evento) => definirValidade(evento.target.value)}
                  required
                />
              </div>
            </label>
          </div>

          <label className="campo-formulario">
            <span>Observações e condições comerciais</span>
            <div>
              <textarea
                value={observacoes}
                onChange={(evento) => definirObservacoes(evento.target.value)}
                placeholder="Prazo de entrega, garantia, condições de pagamento..."
              />
            </div>
          </label>

          <div className="resumo-total-orcamento">
            <div>
              <span>Subtotal</span>
              <strong>{formatoMoeda.format(subtotal)}</strong>
            </div>
            <div>
              <span>Desconto</span>
              <strong>- {formatoMoeda.format(Number(desconto || 0))}</strong>
            </div>
            <div className="total-orcamento">
              <span>Valor da proposta</span>
              <strong>{formatoMoeda.format(valorTotal)}</strong>
            </div>
          </div>

          <button
            className="botao-principal"
            disabled={salvando || !itens.length}
          >
            <ReceiptText size={16} />
            {salvando ? "Salvando..." : "Criar orçamento"}
          </button>
        </form>

        <section className="lista-estoque lista-orcamentos">
          <div className="barra-lista">
            <div>
              <h2>Orçamentos emitidos</h2>
              <small>{orcamentos.length} propostas no histórico</small>
            </div>
          </div>
          {orcamentos.length === 0 ? (
            <div className="estado-vazio">
              <FileText size={30} />
              <h3>Nenhum orçamento emitido</h3>
              <p>As propostas criadas aparecerão aqui.</p>
            </div>
          ) : (
            <div className="grade-cartoes-orcamentos">
              {orcamentos.map((item) => (
                <article key={item.id}>
                  <div className="cabecalho-orcamento">
                    <div>
                      <span>ORÇAMENTO #{String(item.id).padStart(5, "0")}</span>
                      <h3>{item.nome_cliente || "Consumidor não identificado"}</h3>
                    </div>
                    <span className={`status-comercial ${item.status}`}>
                      {item.status}
                    </span>
                  </div>

                  <div className="dados-orcamento-emitido">
                    <span>
                      <CalendarDays size={12} />
                      Válido até {new Date(`${item.validade}T12:00:00`).toLocaleDateString("pt-BR")}
                    </span>
                    {item.cliente_whatsapp && (
                      <span><Phone size={12} /> {item.cliente_whatsapp}</span>
                    )}
                    {item.cliente_email && (
                      <span><Mail size={12} /> {item.cliente_email}</span>
                    )}
                  </div>

                  <div className="itens-orcamento-emitido">
                    {item.itens.map((produto) => (
                      <div key={produto.id}>
                        <span>{produto.quantidade}x {produto.nome_produto}</span>
                        <strong>{formatoMoeda.format(produto.valor_total)}</strong>
                      </div>
                    ))}
                  </div>

                  <div className="resumo-orcamento">
                    <span>{item.itens.length} produto(s)</span>
                    <strong>{formatoMoeda.format(item.valor_total)}</strong>
                  </div>

                  <div className="acoes-orcamento">
                    <button onClick={() => baixarPdf(item)}>
                      <FileText size={14} /> Baixar PDF
                    </button>
                    <button onClick={() => compartilhar(item, "whatsapp")}>
                      <MessageCircle size={14} /> WhatsApp
                    </button>
                    <button onClick={() => compartilhar(item, "email")}>
                      <Mail size={14} /> E-mail
                    </button>
                    {item.status === "pendente" && (
                      <button
                        className="converter"
                        onClick={() => abrirConversao(item)}
                      >
                        <ShoppingCart size={14} /> Converter em Venda
                      </button>
                    )}
                    {item.status === "pendente" && (
                      <button
                        className="cancelar"
                        onClick={() => cancelar(item)}
                        aria-label={`Cancelar orçamento ${item.id}`}
                      >
                        <XCircle size={14} />
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </section>

      {orcamentoConversao && (
        <div className="fundo-modal">
          <article className="modal-conversao-orcamento">
            <button
              className="fechar-modal"
              onClick={() => definirOrcamentoConversao(null)}
              aria-label="Fechar conversão"
            >
              <X size={18} />
            </button>
            <div className="icone-conversao-orcamento">
              <ShoppingCart size={23} />
            </div>
            <span>CONVERTER EM VENDA</span>
            <h2>Orçamento #{String(orcamentoConversao.id).padStart(5, "0")}</h2>
            <p>
              A venda será vinculada a {orcamentoConversao.nome_cliente || "consumidor não identificado"}.
              Os itens, estoque, financeiro e relatórios serão atualizados automaticamente.
            </p>
            <div className="resumo-conversao-orcamento">
              <span>Valor da venda</span>
              <strong>{formatoMoeda.format(orcamentoConversao.valor_total)}</strong>
            </div>
            <label className="campo-formulario">
              <span>Forma de pagamento</span>
              <div>
                <select
                  value={formaPagamento}
                  onChange={(evento) => definirFormaPagamento(evento.target.value)}
                >
                  {Object.entries(nomesPagamento).map(([valor, nome]) => (
                    <option key={valor} value={valor}>{nome}</option>
                  ))}
                </select>
              </div>
            </label>
            {formaPagamento === "pix" && (
              <p className="aviso-conversao-pix">
                No PIX, a venda ficará aguardando pagamento até a confirmação.
              </p>
            )}
            <div className="acoes-modal-orcamento">
              <button
                type="button"
                onClick={() => definirOrcamentoConversao(null)}
              >
                Voltar
              </button>
              <button
                type="button"
                className="confirmar"
                disabled={convertendo}
                onClick={confirmarConversao}
              >
                <ShoppingCart size={15} />
                {convertendo ? "Convertendo..." : "Confirmar venda"}
              </button>
            </div>
          </article>
        </div>
      )}
    </main>
  );
}
