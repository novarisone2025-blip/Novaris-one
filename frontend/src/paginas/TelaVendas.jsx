import { useEffect, useMemo, useRef, useState } from "react";
import {
  Barcode,
  Banknote,
  CheckCircle2,
  Clock3,
  Copy,
  Minus,
  PackageSearch,
  Plus,
  Printer,
  QrCode,
  ReceiptText,
  Search,
  ShoppingCart,
  Trash2,
  LockKeyhole,
  ArrowDownToLine,
  ArrowUpFromLine,
} from "lucide-react";

import {
  baixarComprovanteVenda,
  baixarRelatorioCaixa,
  abrirCaixa,
  buscarProdutoVenda,
  buscarCaixaAtual,
  buscarStatusPagamentoVenda,
  confirmarPagamentoVenda,
  fecharCaixa,
  listarClientes,
  pesquisarProdutosVenda,
  registrarVenda,
  registrarReforco,
  registrarSangria,
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


export function TelaVendas({ aoRegistrarVenda }) {
  const { possuiPermissao } = usarAutenticacao();
  const [codigoBarras, definirCodigoBarras] = useState("");
  const [modoBusca, definirModoBusca] = useState("codigo");
  const [nomeProduto, definirNomeProduto] = useState("");
  const [resultadosPesquisa, definirResultadosPesquisa] = useState([]);
  const [ultimoProdutoAdicionado, definirUltimoProdutoAdicionado] = useState(null);
  const [carrinho, definirCarrinho] = useState([]);
  const [desconto, definirDesconto] = useState("0");
  const [formaPagamento, definirFormaPagamento] = useState("dinheiro");
  const [valorRecebido, definirValorRecebido] = useState("");
  const [clientes, definirClientes] = useState([]);
  const [clienteId, definirClienteId] = useState("");
  const [resultado, definirResultado] = useState(null);
  const [mensagemErro, definirMensagemErro] = useState("");
  const [buscando, definirBuscando] = useState(false);
  const [salvando, definirSalvando] = useState(false);
  const [caixa, definirCaixa] = useState(undefined);
  const [valorInicial, definirValorInicial] = useState("");
  const [valorReal, definirValorReal] = useState("");
  const [mostrandoFechamento, definirMostrandoFechamento] = useState(false);
  const [caixaFechado, definirCaixaFechado] = useState(null);
  const [operacaoCaixa, definirOperacaoCaixa] = useState(null);
  const [valorOperacaoCaixa, definirValorOperacaoCaixa] = useState("");
  const [motivoOperacaoCaixa, definirMotivoOperacaoCaixa] = useState("");
  const campoCodigo = useRef(null);
  const codigoEmProcessamento = useRef("");
  const podeSangria = possuiPermissao("caixa_sangria");
  const podeReforco = possuiPermissao("caixa_reforco");

  const subtotal = useMemo(
    () => carrinho.reduce(
      (total, item) => total + Number(item.preco) * item.quantidade,
      0,
    ),
    [carrinho],
  );
  const valorDesconto = Math.max(Number(desconto || 0), 0);
  const valorFinal = Math.max(subtotal - valorDesconto, 0);
  const valorRecebidoNumerico = Math.max(
    Number(valorRecebido || 0),
    0,
  );
  const faltaPagamento = formaPagamento === "dinheiro"
    ? Math.max(valorFinal - valorRecebidoNumerico, 0)
    : 0;
  const trocoPagamento = formaPagamento === "dinheiro"
    ? Math.max(valorRecebidoNumerico - valorFinal, 0)
    : 0;
  const pagamentoDinheiroValido = formaPagamento !== "dinheiro"
    || (valorRecebido !== "" && faltaPagamento === 0);
  const totalUnidades = carrinho.reduce(
    (total, item) => total + item.quantidade,
    0,
  );

  useEffect(() => {
    carregarCaixa();
    if (possuiPermissao("clientes_visualizar")) carregarClientes();
  }, []);

  useEffect(() => {
    if (
      !resultado
      || resultado.status !== "aguardando_pagamento"
      || !resultado.confirmacao_automatica
    ) {
      return undefined;
    }
    const intervalo = window.setInterval(async () => {
      try {
        const statusPagamento = await buscarStatusPagamentoVenda(resultado.id);
        if (statusPagamento.status === "pago") {
          definirResultado((atual) => ({
            ...atual,
            status: "pago",
            status_cobranca: "pago",
            data_pagamento: statusPagamento.data_pagamento,
          }));
          definirCaixa(await buscarCaixaAtual());
          aoRegistrarVenda?.();
        }
      } catch {
        // Uma falha momentanea nao interrompe a venda nem o modo manual.
      }
    }, 3000);
    return () => window.clearInterval(intervalo);
  }, [
    aoRegistrarVenda,
    resultado?.confirmacao_automatica,
    resultado?.id,
    resultado?.status,
  ]);

  async function carregarClientes() {
    try {
      definirClientes(await listarClientes());
    } catch {
      definirClientes([]);
    }
  }

  async function carregarCaixa() {
    try {
      definirCaixa(await buscarCaixaAtual());
    } catch (erro) {
      definirMensagemErro(erro.message);
      definirCaixa(null);
    }
  }

  async function iniciarExpediente(evento) {
    evento.preventDefault();
    definirSalvando(true);
    definirMensagemErro("");
    try {
      definirCaixa(await abrirCaixa(valorInicial || 0));
      definirValorInicial("");
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function prepararFechamento() {
    definirMensagemErro("");
    try {
      const resumo = await buscarCaixaAtual();
      definirCaixa(resumo);
      definirValorReal(String(resumo.valor_esperado));
      definirMostrandoFechamento(true);
    } catch (erro) {
      definirMensagemErro(erro.message);
    }
  }

  async function concluirFechamento(evento) {
    evento.preventDefault();
    definirSalvando(true);
    definirMensagemErro("");
    try {
      const resposta = await fecharCaixa(valorReal);
      definirCaixaFechado(resposta);
      definirCaixa(null);
      definirMostrandoFechamento(false);
      definirCarrinho([]);
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirSalvando(false);
    }
  }

  useEffect(() => {
    const codigo = codigoBarras.trim();
    if (codigo.length < 3) {
      return undefined;
    }
    const espera = window.setTimeout(() => adicionarCodigoAoCarrinho(codigo), 700);
    return () => window.clearTimeout(espera);
  }, [codigoBarras]);

  async function adicionarCodigoAoCarrinho(codigoInformado) {
    const codigo = codigoInformado.trim();
    if (!codigo || codigoEmProcessamento.current === codigo) return;
    codigoEmProcessamento.current = codigo;
    definirMensagemErro("");
    definirBuscando(true);
    try {
      const produto = await buscarProdutoVenda(codigo);
      if (adicionarProduto(produto)) {
        definirUltimoProdutoAdicionado(produto);
        definirCodigoBarras("");
        definirResultado(null);
      }
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirBuscando(false);
      codigoEmProcessamento.current = "";
      window.setTimeout(() => campoCodigo.current?.focus(), 0);
    }
  }

  function receberLeitura(evento) {
    evento?.preventDefault();
    const codigo = codigoBarras.trim();
    adicionarCodigoAoCarrinho(codigo);
  }

  async function pesquisarPorNome(evento) {
    evento.preventDefault();
    const nome = nomeProduto.trim();
    if (nome.length < 2) {
      definirMensagemErro("Digite pelo menos duas letras do produto.");
      return;
    }
    definirBuscando(true);
    definirMensagemErro("");
    try {
      definirResultadosPesquisa(await pesquisarProdutosVenda(nome));
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirBuscando(false);
    }
  }

  function adicionarResultadoPesquisa(produto) {
    if (adicionarProduto(produto)) {
      definirUltimoProdutoAdicionado(produto);
      definirResultado(null);
    }
  }

  function adicionarProduto(produto) {
    const existente = carrinho.find((item) => item.id === produto.id);
    if (produto.quantidade < 1) {
      definirMensagemErro("Este produto está sem estoque.");
      return false;
    }
    if (existente && existente.quantidade >= produto.quantidade) {
      definirMensagemErro("A quantidade do carrinho atingiu o estoque disponível.");
      return false;
    }

    definirCarrinho((itens) => {
      const itemExistente = itens.find(
        (item) => item.id === produto.id,
      );
      if (itemExistente) {
        return itens.map((item) =>
          item.id === produto.id
            ? { ...item, quantidade: item.quantidade + 1 }
            : item
        );
      }
      return [
        ...itens,
        {
          ...produto,
          estoque_disponivel: produto.quantidade,
          quantidade: 1,
        },
      ];
    });
    return true;
  }

  function alterarQuantidade(produtoId, diferenca) {
    definirCarrinho((itens) =>
      itens
        .map((item) => {
          if (item.id !== produtoId) return item;
          const quantidade = Math.min(
            Math.max(item.quantidade + diferenca, 0),
            item.quantidade,
          );
          return { ...item, quantidade };
        })
        .filter((item) => item.quantidade > 0)
    );
  }

  function removerItem(produtoId) {
    definirCarrinho((itens) =>
      itens.filter((item) => item.id !== produtoId)
    );
  }

  async function concluirVenda() {
    if (!carrinho.length) {
      definirMensagemErro("Adicione pelo menos um produto ao carrinho.");
      return;
    }
    if (valorDesconto > subtotal) {
      definirMensagemErro("O desconto não pode ser maior que o subtotal.");
      return;
    }
    if (!pagamentoDinheiroValido) {
      definirMensagemErro(
        valorRecebido === ""
          ? "Informe o valor recebido do cliente."
          : `Faltam ${formatoMoeda.format(faltaPagamento)} para completar o pagamento.`,
      );
      return;
    }
    definirMensagemErro("");
    definirSalvando(true);
    try {
      const resposta = await registrarVenda(
        carrinho.map((item) => ({
          codigo_barras: item.codigo_barras,
          quantidade: item.quantidade,
        })),
        valorDesconto,
        formaPagamento,
        clienteId ? Number(clienteId) : null,
        formaPagamento === "dinheiro" ? valorRecebidoNumerico : null,
      );
      definirResultado(resposta);
      definirCarrinho([]);
      definirDesconto("0");
      definirValorRecebido("");
      definirClienteId("");
      definirUltimoProdutoAdicionado(null);
      await carregarCaixa();
      if (resposta.status === "pago") {
        aoRegistrarVenda();
      }
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function confirmarPagamento(vendaId) {
    definirSalvando(true);
    definirMensagemErro("");
    try {
      const resposta = await confirmarPagamentoVenda(vendaId);
      definirResultado(resposta);
      await carregarCaixa();
      aoRegistrarVenda();
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function concluirOperacaoCaixa(evento) {
    evento.preventDefault();
    definirSalvando(true);
    definirMensagemErro("");
    try {
      if (operacaoCaixa === "sangria") {
        await registrarSangria(valorOperacaoCaixa, motivoOperacaoCaixa);
      } else {
        await registrarReforco(valorOperacaoCaixa, motivoOperacaoCaixa);
      }
      definirOperacaoCaixa(null);
      definirValorOperacaoCaixa("");
      definirMotivoOperacaoCaixa("");
      await carregarCaixa();
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function copiarCodigoPix() {
    await navigator.clipboard.writeText(resultado.codigo_pix);
  }

  function imprimirComprovante() {
    window.print();
  }

  return (
    <main className="conteudo-dashboard conteudo-vendas">
      <div className="cabecalho-pagina">
        <div>
          <span>FRENTE DE CAIXA</span>
          <h1>Nova venda</h1>
          <p>Leia os produtos, revise o carrinho e finalize o pagamento.</p>
        </div>
        {caixa && (
          <div className="acoes-caixa-pdv">
            {podeSangria && <button onClick={() => definirOperacaoCaixa("sangria")}><ArrowDownToLine size={16} /> Sangria</button>}
            {podeReforco && <button onClick={() => definirOperacaoCaixa("reforco")}><ArrowUpFromLine size={16} /> Reforco</button>}
            <button className="botao-fechar-caixa" onClick={prepararFechamento}>
              <LockKeyhole size={16} /> Fechar caixa
            </button>
          </div>
        )}
      </div>

      {caixa === undefined ? (
        <p>Verificando caixa...</p>
      ) : !caixa ? (
        <section className="painel-abertura-caixa">
          <div>
            <Banknote size={34} />
            <span>INÍCIO DO EXPEDIENTE</span>
            <h2>Abra seu caixa para começar</h2>
            <p>Informe quanto dinheiro existe na gaveta antes da primeira venda.</p>
          </div>
          <form onSubmit={iniciarExpediente}>
            <label><span>Valor inicial em dinheiro</span><div><b>R$</b><input type="number" min="0" step="0.01" value={valorInicial} onChange={(e) => definirValorInicial(e.target.value)} placeholder="0,00" required /></div></label>
            {mensagemErro && <p className="mensagem-erro">{mensagemErro}</p>}
            <button className="botao-principal" disabled={salvando}><Banknote size={16} /> {salvando ? "Abrindo..." : "Abrir caixa"}</button>
          </form>
        </section>
      ) : (
      <>
      <article className="faixa-caixa-aberto">
        <div><span>CAIXA ABERTO</span><strong>#{caixa.id} · {caixa.nome_usuario}</strong></div>
        <div><span>Valor inicial</span><strong>{formatoMoeda.format(caixa.valor_inicial)}</strong></div>
        <div><span>Vendas</span><strong>{caixa.quantidade_vendas}</strong></div>
        <div><span>Dinheiro esperado</span><strong>{formatoMoeda.format(caixa.valor_esperado)}</strong></div>
      </article>

      <section className="caixa-vendas">
        <div className="painel-leitura">
          <div className="abas-busca-pdv">
            <button
              className={modoBusca === "codigo" ? "ativo" : ""}
              onClick={() => definirModoBusca("codigo")}
            >
              <Barcode size={15} /> Leitor de código
            </button>
            <button
              className={modoBusca === "nome" ? "ativo" : ""}
              onClick={() => definirModoBusca("nome")}
            >
              <Search size={15} /> Buscar código pelo nome
            </button>
          </div>

          {modoBusca === "codigo" ? (
            <form className="leitor-barras" onSubmit={receberLeitura}>
              <Barcode size={22} />
              <input
                ref={campoCodigo}
                value={codigoBarras}
                onChange={(evento) => definirCodigoBarras(evento.target.value)}
                placeholder="Digite ou leia o código de barras"
                autoFocus
              />
              <button disabled={buscando}>
                {buscando ? "Adicionando..." : "Adicionar código"}
              </button>
            </form>
          ) : (
            <div className="ferramenta-pesquisa-produto">
              <form className="leitor-barras" onSubmit={pesquisarPorNome}>
                <Search size={22} />
                <input
                  value={nomeProduto}
                  onChange={(evento) => definirNomeProduto(evento.target.value)}
                  placeholder="Digite o nome do produto"
                  autoFocus
                />
                <button disabled={buscando}>
                  {buscando ? "Pesquisando..." : "Pesquisar"}
                </button>
              </form>
              {resultadosPesquisa.length > 0 && (
                <div className="resultados-pesquisa-produto">
                  {resultadosPesquisa.map((produto) => (
                    <article key={produto.id}>
                      <div>
                        <strong>{produto.nome}</strong>
                        <span>Código: {produto.codigo_barras}</span>
                      </div>
                      <div>
                        <small>{formatoMoeda.format(produto.preco)} · {produto.quantidade} em estoque</small>
                        <button onClick={() => adicionarResultadoPesquisa(produto)}>
                          <Plus size={14} /> Adicionar
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
              {!buscando && nomeProduto && resultadosPesquisa.length === 0 && (
                <p className="aviso-pesquisa-produto">
                  Pesquise para localizar o código de barras pelo nome.
                </p>
              )}
            </div>
          )}

          <article className="produto-localizado">
            {ultimoProdutoAdicionado ? (
              <>
                <div className="imagem-produto-venda">
                  {ultimoProdutoAdicionado.imagem_url ? (
                    <img src={ultimoProdutoAdicionado.imagem_url} alt={ultimoProdutoAdicionado.nome} />
                  ) : (
                    <PackageSearch size={34} />
                  )}
                </div>
                <div className="dados-produto-venda">
                  <span>ÚLTIMO ITEM ADICIONADO</span>
                  <h2>{ultimoProdutoAdicionado.nome}</h2>
                  <small>{ultimoProdutoAdicionado.codigo_barras}</small>
                  <div>
                    <strong>{formatoMoeda.format(ultimoProdutoAdicionado.preco)}</strong>
                    <b>Adicionado ao carrinho</b>
                  </div>
                </div>
              </>
            ) : (
              <div className="produto-nao-localizado">
                <PackageSearch size={34} />
                <div>
                  <strong>Aguardando leitura</strong>
                  <span>O produto será adicionado automaticamente ao carrinho.</span>
                </div>
              </div>
            )}
          </article>

          <section className="carrinho-venda">
            <div className="titulo-carrinho">
              <div>
                <ShoppingCart size={19} />
                <h2>Carrinho</h2>
              </div>
              <span>{totalUnidades} item(ns)</span>
            </div>
            {carrinho.length === 0 ? (
              <div className="carrinho-vazio">
                <ShoppingCart size={31} />
                <p>Leia um código de barras para começar.</p>
              </div>
            ) : (
              <div className="lista-carrinho">
                {carrinho.map((item) => (
                  <article key={item.id}>
                    <div className="miniatura-carrinho">
                      {item.imagem_url ? (
                        <img src={item.imagem_url} alt="" />
                      ) : (
                        <PackageSearch size={18} />
                      )}
                    </div>
                    <div className="nome-item-carrinho">
                      <strong>{item.nome}</strong>
                      <small>{formatoMoeda.format(item.preco)} cada</small>
                    </div>
                    <div className="controle-quantidade">
                      <button onClick={() => alterarQuantidade(item.id, -1)}>
                        <Minus size={13} />
                      </button>
                      <b>{item.quantidade}</b>
                      <button
                        onClick={() => definirCarrinho((itens) =>
                          itens.map((produto) =>
                            produto.id === item.id &&
                            produto.quantidade < produto.estoque_disponivel
                              ? { ...produto, quantidade: produto.quantidade + 1 }
                              : produto
                          )
                        )}
                      >
                        <Plus size={13} />
                      </button>
                    </div>
                    <strong>{formatoMoeda.format(Number(item.preco) * item.quantidade)}</strong>
                    <button className="remover-carrinho" onClick={() => removerItem(item.id)}>
                      <Trash2 size={15} />
                    </button>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>

        <aside className="resumo-venda">
          <div className="titulo-resumo-venda">
            <ReceiptText size={20} />
            <div><span>RESUMO</span><h2>Pagamento</h2></div>
          </div>
          <div className="linha-resumo">
            <span>Subtotal</span><strong>{formatoMoeda.format(subtotal)}</strong>
          </div>
          {possuiPermissao("clientes_visualizar") && (
            <label className="campo-pagamento">
              <span>Cliente da venda</span>
              <select value={clienteId} onChange={(evento) => definirClienteId(evento.target.value)}>
                <option value="">Consumidor não identificado</option>
                {clientes.map((cliente) => (
                  <option key={cliente.id} value={cliente.id}>{cliente.nome}</option>
                ))}
              </select>
            </label>
          )}
          <label className="campo-desconto">
            <span>Desconto</span>
            <div><span>R$</span><input type="number" min="0" step="0.01" value={desconto} onChange={(evento) => definirDesconto(evento.target.value)} /></div>
          </label>
          <label className="campo-pagamento">
            <span>Forma de pagamento</span>
            <select
              value={formaPagamento}
              onChange={(evento) => {
                definirFormaPagamento(evento.target.value);
                definirValorRecebido("");
                definirMensagemErro("");
              }}
            >
              {Object.entries(nomesPagamento).map(([valor, nome]) => (
                <option key={valor} value={valor}>{nome}</option>
              ))}
            </select>
          </label>
          {formaPagamento === "dinheiro" && (
            <div className="pagamento-dinheiro">
              <label className="campo-valor-recebido">
                <span>Valor recebido</span>
                <div>
                  <span>R$</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={valorRecebido}
                    onChange={(evento) => {
                      definirValorRecebido(evento.target.value);
                      definirMensagemErro("");
                    }}
                    placeholder="0,00"
                  />
                </div>
              </label>
              <div className={`resultado-troco ${faltaPagamento > 0 ? "faltando" : "suficiente"}`}>
                <span>{faltaPagamento > 0 ? "Falta receber" : "Troco"}</span>
                <strong>
                  {formatoMoeda.format(
                    faltaPagamento > 0 ? faltaPagamento : trocoPagamento,
                  )}
                </strong>
                <small>
                  {valorRecebido === ""
                    ? "Informe quanto o cliente entregou"
                    : faltaPagamento > 0
                      ? "Pagamento insuficiente"
                      : "Valor a devolver ao cliente"}
                </small>
              </div>
            </div>
          )}
          <div className="total-venda">
            <span>Valor final</span>
            <strong>{formatoMoeda.format(valorFinal)}</strong>
          </div>
          {mensagemErro && <p className="mensagem-erro">{mensagemErro}</p>}
          <button
            className="botao-principal"
            disabled={
              salvando
              || !carrinho.length
              || !pagamentoDinheiroValido
            }
            onClick={concluirVenda}
          >
            {salvando ? "Finalizando..." : "Finalizar venda"}
          </button>
        </aside>
      </section>

      </>
      )}

      {resultado && (
        <div className="fundo-modal">
          <article className={`comprovante-venda ${resultado.status === "aguardando_pagamento" ? "pagamento-pendente" : ""}`}>
            {resultado.status === "pago" ? <CheckCircle2 size={45} /> : <Clock3 size={45} />}
            <span>{resultado.status === "pago" ? "VENDA CONCLUÍDA" : "AGUARDANDO PAGAMENTO"}</span>
            <h2>Venda #{resultado.id}</h2>
            <p>{resultado.itens.length} produto(s) • {nomesPagamento[resultado.forma_pagamento]}</p>
            {resultado.forma_pagamento === "dinheiro" && (
              <div className="resumo-dinheiro-comprovante">
                <div>
                  <span>Valor recebido</span>
                  <strong>{formatoMoeda.format(resultado.valor_recebido)}</strong>
                </div>
                <div>
                  <span>Troco entregue</span>
                  <strong>{formatoMoeda.format(resultado.troco_entregue)}</strong>
                </div>
              </div>
            )}
            {resultado.status === "aguardando_pagamento" && (
              <div className="cobranca-pix">
                <div className="qr-code-pix">
                  {resultado.qr_code_pix ? <img src={resultado.qr_code_pix} alt="QR Code PIX" /> : <QrCode size={80} />}
                </div>
                <strong>{formatoMoeda.format(resultado.valor_total)}</strong>
                <span>
                  {resultado.confirmacao_automatica
                    ? "Aguardando confirmação automática do provedor"
                    : "Peça ao cliente para escanear o QR Code"}
                </span>
                <label>
                  <textarea readOnly value={resultado.codigo_pix || ""} />
                  <button onClick={copiarCodigoPix}><Copy size={15} /> Copiar código PIX</button>
                </label>
              </div>
            )}
            <div className="itens-comprovante">
              {resultado.itens.map((item) => (
                <div key={item.produto_id}>
                  <span>{item.quantidade}x {item.nome_produto}</span>
                  <strong>{formatoMoeda.format(item.valor_total)}</strong>
                </div>
              ))}
            </div>
            {resultado.status === "pago" ? (
              <>
                <strong>{formatoMoeda.format(resultado.valor_total)}</strong>
                <div className="acoes-comprovante">
                  <button onClick={imprimirComprovante}><Printer size={16} /> Imprimir</button>
                  <button onClick={() => baixarComprovanteVenda(resultado.id)}><ReceiptText size={16} /> Baixar PDF</button>
                </div>
                <button className="botao-principal" onClick={() => definirResultado(null)}>Nova venda</button>
              </>
            ) : (
              <>
                <button className="botao-principal" disabled={salvando} onClick={() => confirmarPagamento(resultado.id)}>
                  <CheckCircle2 size={16} /> {salvando ? "Confirmando..." : "Marcar como pago"}
                </button>
                <button className="botao-fechar-pix" onClick={() => definirResultado(null)}>Fechar e confirmar depois</button>
              </>
            )}
          </article>
        </div>
      )}

      {mostrandoFechamento && caixa && (
        <div className="fundo-modal">
          <form className="modal-fechamento-caixa" onSubmit={concluirFechamento}>
            <Banknote size={36} />
            <span>FECHAMENTO DO EXPEDIENTE</span>
            <h2>Conferência do caixa #{caixa.id}</h2>
            <div className="grade-resumo-caixa">
              <div><span>Dinheiro</span><strong>{formatoMoeda.format(caixa.total_dinheiro)}</strong></div>
              <div><span>Recebido em espécie</span><strong>{formatoMoeda.format(caixa.total_recebido_dinheiro)}</strong></div>
              <div><span>Troco entregue</span><strong>{formatoMoeda.format(caixa.total_troco_entregue)}</strong></div>
              <div><span>PIX</span><strong>{formatoMoeda.format(caixa.total_pix)}</strong></div>
              <div><span>Débito</span><strong>{formatoMoeda.format(caixa.total_debito)}</strong></div>
              <div><span>Crédito</span><strong>{formatoMoeda.format(caixa.total_credito)}</strong></div>
              <div><span>Descontos</span><strong>{formatoMoeda.format(caixa.total_descontos)}</strong></div>
              <div><span>Cancelamentos</span><strong>{formatoMoeda.format(caixa.total_cancelamentos)}</strong></div>
            </div>
            <div className="valor-esperado-caixa"><span>Valor esperado na gaveta</span><strong>{formatoMoeda.format(caixa.valor_esperado)}</strong><small>Valor inicial + vendas em dinheiro</small></div>
            <label className="campo-valor-real"><span>Valor real contado</span><div><b>R$</b><input type="number" min="0" step="0.01" value={valorReal} onChange={(e) => definirValorReal(e.target.value)} required /></div></label>
            {mensagemErro && <p className="mensagem-erro">{mensagemErro}</p>}
            <button className="botao-principal" disabled={salvando}>{salvando ? "Fechando..." : "Confirmar fechamento"}</button>
            <button type="button" className="botao-fechar-pix" onClick={() => definirMostrandoFechamento(false)}>Voltar ao caixa</button>
          </form>
        </div>
      )}

      {caixaFechado && (
        <div className="fundo-modal">
          <article className="modal-fechamento-caixa resultado-fechamento">
            <CheckCircle2 size={42} />
            <span>CAIXA FECHADO</span>
            <h2>{caixaFechado.situacao_diferenca === "correto" ? "Valores conferem" : caixaFechado.situacao_diferenca === "sobra" ? "Sobra de caixa" : "Falta de caixa"}</h2>
            <div className={`diferenca-caixa ${caixaFechado.situacao_diferenca}`}><span>Diferença</span><strong>{formatoMoeda.format(caixaFechado.diferenca)}</strong></div>
            <button className="botao-principal" onClick={() => baixarRelatorioCaixa(caixaFechado.id)}><ReceiptText size={16} /> Baixar relatório PDF</button>
            <button className="botao-fechar-pix" onClick={() => definirCaixaFechado(null)}>Fechar</button>
          </article>
        </div>
      )}

      {operacaoCaixa && (
        <div className="fundo-modal">
          <form className="modal-movimentacao modal-operacao-caixa" onSubmit={concluirOperacaoCaixa}>
            {operacaoCaixa === "sangria" ? <ArrowDownToLine size={28} /> : <ArrowUpFromLine size={28} />}
            <span>{operacaoCaixa === "sangria" ? "RETIRADA DE DINHEIRO" : "ENTRADA ADICIONAL"}</span>
            <h2>{operacaoCaixa === "sangria" ? "Registrar sangria" : "Registrar reforco"}</h2>
            <label className="campo-formulario"><span>Valor</span><div><span>R$</span><input type="number" min="0.01" step="0.01" value={valorOperacaoCaixa} onChange={(e) => definirValorOperacaoCaixa(e.target.value)} required autoFocus /></div></label>
            <label className="campo-formulario"><span>Motivo obrigatorio</span><div><textarea minLength="5" maxLength="500" value={motivoOperacaoCaixa} onChange={(e) => definirMotivoOperacaoCaixa(e.target.value)} required /></div></label>
            {mensagemErro && <p className="mensagem-erro">{mensagemErro}</p>}
            <button className="botao-principal" disabled={salvando}>{salvando ? "Registrando..." : "Confirmar operacao"}</button>
            <button type="button" className="botao-cancelar-usuario" onClick={() => definirOperacaoCaixa(null)}>Voltar</button>
          </form>
        </div>
      )}
    </main>
  );
}
