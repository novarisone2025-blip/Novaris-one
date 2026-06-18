import { useEffect, useMemo, useState } from "react";
import {
  Barcode,
  Boxes,
  Minus,
  Pencil,
  Plus,
  Search,
  Trash2,
  FileSpreadsheet,
  FileText,
  TriangleAlert,
  X,
} from "lucide-react";

import {
  atualizarProduto,
  cadastrarProduto,
  excluirProduto,
  listarProdutos,
  listarFornecedores,
  registrarMovimentacao,
  baixarRelatorioEstoque,
} from "../servicos/servicoApi";
import { usarAutenticacao } from "../contexts/ContextoAutenticacao";


const formularioVazio = {
  codigo_barras: "",
  nome: "",
  categoria: "Sem categoria",
  quantidade: "",
  estoque_minimo: "",
  preco: "",
  preco_compra: "",
  fornecedor_id: "",
  imagem_url: "",
};


export function TelaEstoque({ aoAlterarEstoque }) {
  const { usuario, possuiPermissao } = usarAutenticacao();
  const [produtos, definirProdutos] = useState([]);
  const [fornecedores, definirFornecedores] = useState([]);
  const [busca, definirBusca] = useState("");
  const [formulario, definirFormulario] = useState(formularioVazio);
  const [produtoEmEdicao, definirProdutoEmEdicao] = useState(null);
  const [movimentacao, definirMovimentacao] = useState(null);
  const [quantidadeMovimento, definirQuantidadeMovimento] = useState("1");
  const [mensagemErro, definirMensagemErro] = useState("");
  const [carregando, definirCarregando] = useState(true);
  const [salvando, definirSalvando] = useState(false);
  const podeCadastrarProdutos = (
    usuario?.cargo !== "Caixa"
    && (
      possuiPermissao("estoque_gerenciar")
      || possuiPermissao("produtos_cadastrar")
    )
  );
  const podeEditarProdutos = (
    usuario?.cargo !== "Caixa"
    && (
      possuiPermissao("estoque_gerenciar")
      || possuiPermissao("produtos_editar")
    )
  );
  const podeExcluirProdutos = (
    usuario?.cargo !== "Caixa"
    && (
      possuiPermissao("estoque_gerenciar")
      || possuiPermissao("produtos_excluir")
    )
  );
  const podeGerenciarProdutos = podeCadastrarProdutos || podeEditarProdutos;
  const podeMovimentarEstoque = possuiPermissao("estoque_movimentar");
  const podeGerarRelatorios = possuiPermissao("relatorios_gerar");
  const podeVerAlertas = (
    ["Administrador", "Gerente", "Estoquista", "Estoque"].includes(
      usuario?.cargo,
    )
  );

  useEffect(() => {
    carregarProdutos();
    listarFornecedores()
      .then(definirFornecedores)
      .catch(() => definirFornecedores([]));
  }, []);

  async function carregarProdutos() {
    definirCarregando(true);
    try {
      const resposta = await listarProdutos();
      definirProdutos(resposta);
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirCarregando(false);
    }
  }

  function atualizarCampo(evento) {
    definirFormulario({
      ...formulario,
      [evento.target.name]: evento.target.value,
    });
  }

  function iniciarEdicao(produto) {
    definirProdutoEmEdicao(produto);
    definirFormulario({
      codigo_barras: produto.codigo_barras,
      nome: produto.nome,
      categoria: produto.categoria,
      quantidade: produto.quantidade,
      estoque_minimo: produto.estoque_minimo,
      preco: produto.preco,
      preco_compra: produto.preco_compra,
      fornecedor_id: produto.fornecedor_id || "",
      imagem_url: produto.imagem_url || "",
    });
    definirMensagemErro("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function cancelarEdicao() {
    definirProdutoEmEdicao(null);
    definirFormulario(formularioVazio);
    definirMensagemErro("");
  }

  async function salvarProduto(evento) {
    evento.preventDefault();
    definirMensagemErro("");
    definirSalvando(true);

    const dadosBasicos = {
      codigo_barras: formulario.codigo_barras,
      nome: formulario.nome,
      categoria: formulario.categoria,
      preco: Number(formulario.preco),
      preco_compra: Number(formulario.preco_compra || 0),
      fornecedor_id: formulario.fornecedor_id
        ? Number(formulario.fornecedor_id)
        : null,
      estoque_minimo: Number(formulario.estoque_minimo || 0),
      imagem_url: formulario.imagem_url || null,
    };

    try {
      if (produtoEmEdicao) {
        await atualizarProduto(produtoEmEdicao.id, dadosBasicos);
      } else {
        await cadastrarProduto({
          ...dadosBasicos,
          quantidade: Number(formulario.quantidade || 0),
        });
      }
      cancelarEdicao();
      await carregarProdutos();
      aoAlterarEstoque();
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirSalvando(false);
    }
  }

  function abrirMovimentacao(produto, tipo) {
    definirMovimentacao({ produto, tipo });
    definirQuantidadeMovimento("1");
    definirMensagemErro("");
  }

  async function confirmarMovimentacao(evento) {
    evento.preventDefault();
    definirSalvando(true);
    definirMensagemErro("");

    try {
      await registrarMovimentacao(
        movimentacao.produto.id,
        movimentacao.tipo,
        Number(quantidadeMovimento),
      );
      definirMovimentacao(null);
      await carregarProdutos();
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function removerProduto(produto) {
    const confirmou = window.confirm(
      `Deseja excluir o produto "${produto.nome}"?`,
    );
    if (!confirmou) return;

    try {
      await excluirProduto(produto.id);
      await carregarProdutos();
      aoAlterarEstoque();
    } catch (erro) {
      definirMensagemErro(erro.message);
    }
  }

  const produtosFiltrados = useMemo(() => {
    const termo = busca.toLowerCase().trim();
    if (!termo) return produtos;
    return produtos.filter(
      (produto) =>
        produto.nome.toLowerCase().includes(termo) ||
        produto.codigo_barras.toLowerCase().includes(termo),
    );
  }, [produtos, busca]);

  const valorEstoque = produtos.reduce(
    (total, produto) =>
      total + Number(produto.preco) * produto.quantidade,
    0,
  );
  const unidadesEstoque = produtos.reduce(
    (total, produto) => total + produto.quantidade,
    0,
  );
  const produtosComAlerta = produtos.filter(
    (produto) => produto.quantidade <= produto.estoque_minimo,
  );
  const formatoMoeda = new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  });

  return (
    <main className="conteudo-dashboard conteudo-estoque">
      <div className="cabecalho-pagina">
        <div>
          <span>CONTROLE DE ESTOQUE</span>
          <h1>Produtos</h1>
          <p>Cadastre produtos e acompanhe entradas e vendas.</p>
        </div>
        {podeGerarRelatorios && <div className="acoes-relatorio">
          <button onClick={() => baixarRelatorioEstoque("pdf")}>
            <FileText size={16} /> PDF
          </button>
          <button onClick={() => baixarRelatorioEstoque("excel")}>
            <FileSpreadsheet size={16} /> Excel
          </button>
        </div>}
      </div>

      <div className="resumo-estoque">
        <article>
          <Boxes size={21} />
          <div><span>Produtos</span><strong>{produtos.length}</strong></div>
        </article>
        {podeVerAlertas && <article className={produtosComAlerta.length ? "resumo-alerta" : ""}>
          <TriangleAlert size={21} />
          <div><span>Estoque baixo</span><strong>{produtosComAlerta.length}</strong></div>
        </article>}
        <article>
          <Barcode size={21} />
          <div><span>Unidades em estoque</span><strong>{unidadesEstoque}</strong></div>
        </article>
        <article>
          <span className="simbolo-real">R$</span>
          <div><span>Valor do estoque</span><strong>{formatoMoeda.format(valorEstoque)}</strong></div>
        </article>
      </div>

      <section className={`grade-estoque ${!podeGerenciarProdutos ? "somente-lista" : ""}`}>
        {(podeCadastrarProdutos || (produtoEmEdicao && podeEditarProdutos)) && <form className="formulario-produto" onSubmit={salvarProduto}>
          <div className="titulo-formulario-produto">
            <div>
              <span>{produtoEmEdicao ? "EDITAR PRODUTO" : "NOVO PRODUTO"}</span>
              <h2>
                {produtoEmEdicao
                  ? "Atualize os dados"
                  : "Cadastre um produto"}
              </h2>
            </div>
            {produtoEmEdicao && (
              <button type="button" onClick={cancelarEdicao}>
                <X size={18} />
              </button>
            )}
          </div>

          <label className="campo-formulario">
            <span>Código de barras</span>
            <div>
              <Barcode size={18} />
              <input
                name="codigo_barras"
                value={formulario.codigo_barras}
                onChange={atualizarCampo}
                placeholder="Digite ou use o leitor"
                required
              />
            </div>
          </label>

          <label className="campo-formulario">
            <span>Nome do produto</span>
            <div>
              <Boxes size={18} />
              <input
                name="nome"
                value={formulario.nome}
                onChange={atualizarCampo}
                placeholder="Ex.: Café tradicional 500g"
                required
              />
            </div>
          </label>

          <label className="campo-formulario">
            <span>Categoria</span>
            <div>
              <Boxes size={18} />
              <input
                name="categoria"
                value={formulario.categoria}
                onChange={atualizarCampo}
                placeholder="Ex.: Bebidas"
                required
              />
            </div>
          </label>

          <label className="campo-formulario">
            <span>Imagem do produto (opcional)</span>
            <div>
              <input
                name="imagem_url"
                type="url"
                value={formulario.imagem_url}
                onChange={atualizarCampo}
                placeholder="https://site.com/imagem.jpg"
              />
            </div>
          </label>

          <div className="duas-colunas">
            {!produtoEmEdicao && (
              <label className="campo-formulario">
                <span>Quantidade inicial</span>
                <div>
                  <input
                    name="quantidade"
                    type="number"
                    min="0"
                    value={formulario.quantidade}
                    onChange={atualizarCampo}
                    placeholder="0"
                    required
                  />
                </div>
              </label>
            )}
            <label className="campo-formulario">
              <span>Preço de compra</span>
              <div>
                <span>R$</span>
                <input
                  name="preco_compra"
                  type="number"
                  min="0"
                  step="0.01"
                  value={formulario.preco_compra}
                  onChange={atualizarCampo}
                  placeholder="0,00"
                />
              </div>
            </label>
            <label className="campo-formulario">
              <span>Preço de venda</span>
              <div>
                <span>R$</span>
                <input
                  name="preco"
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={formulario.preco}
                  onChange={atualizarCampo}
                  placeholder="0,00"
                  required
                />
              </div>
            </label>
            <label className="campo-formulario">
              <span>Estoque mínimo</span>
              <div>
                <input
                  name="estoque_minimo"
                  type="number"
                  min="0"
                  value={formulario.estoque_minimo}
                  onChange={atualizarCampo}
                  placeholder="0"
                  required
                />
              </div>
            </label>
          </div>

          <label className="campo-formulario">
            <span>Fornecedor</span>
            <div>
              <select
                name="fornecedor_id"
                value={formulario.fornecedor_id}
                onChange={atualizarCampo}
              >
                <option value="">Sem fornecedor vinculado</option>
                {fornecedores.map((fornecedor) => (
                  <option key={fornecedor.id} value={fornecedor.id}>
                    {fornecedor.nome}
                  </option>
                ))}
              </select>
            </div>
          </label>

          {mensagemErro && !movimentacao && (
            <p className="mensagem-erro">{mensagemErro}</p>
          )}

          <button className="botao-principal" disabled={salvando}>
            {salvando
              ? "Salvando..."
              : produtoEmEdicao
                ? "Salvar alterações"
                : "Cadastrar produto"}
          </button>
        </form>}

        <section className="lista-estoque">
          <div className="barra-lista">
            <div>
              <h2>Produtos cadastrados</h2>
              <small>{produtosFiltrados.length} itens encontrados</small>
            </div>
            <label className="campo-busca">
              <Search size={17} />
              <input
                value={busca}
                onChange={(evento) => definirBusca(evento.target.value)}
                placeholder="Buscar nome ou código..."
              />
            </label>
          </div>

          {carregando ? (
            <p className="estado-lista">Carregando produtos...</p>
          ) : produtosFiltrados.length === 0 ? (
            <div className="estado-vazio">
              <Boxes size={35} />
              <h3>Nenhum produto encontrado</h3>
              <p>Cadastre o primeiro produto usando o formulário.</p>
            </div>
          ) : (
            <div className="tabela-responsiva">
              <table className="tabela-produtos">
                <thead>
                  <tr>
                    <th>Produto</th>
                    <th>Compra / Venda</th>
                    <th>Estoque</th>
                    {(podeMovimentarEstoque || podeEditarProdutos || podeExcluirProdutos) && <th>Ações</th>}
                  </tr>
                </thead>
                <tbody>
                  {produtosFiltrados.map((produto) => (
                    <tr
                      key={produto.id}
                      className={
                        podeVerAlertas
                        && produto.quantidade <= produto.estoque_minimo
                          ? "produto-em-alerta"
                          : ""
                      }
                    >
                      <td>
                        <div className="identificacao-produto">
                          {produto.imagem_url ? (
                            <img src={produto.imagem_url} alt="" />
                          ) : (
                            <span><Boxes size={15} /></span>
                          )}
                          <div>
                            <strong>{produto.nome}</strong>
                            <small>{produto.categoria} · {produto.codigo_barras}</small>
                          </div>
                        </div>
                      </td>
                      <td>
                        <small className="preco-compra">
                          Custo {formatoMoeda.format(produto.preco_compra)}
                        </small>
                        <strong>{formatoMoeda.format(produto.preco)}</strong>
                        <small className="margem-produto">
                          Lucro {formatoMoeda.format(
                            Number(produto.preco) - Number(produto.preco_compra),
                          )}
                        </small>
                      </td>
                      <td>
                        <span className={produto.quantidade === 0 ? "sem-estoque" : "com-estoque"}>
                          {produto.quantidade} un.
                        </span>
                        {podeVerAlertas && produto.quantidade <= produto.estoque_minimo && (
                          <small className="texto-reposicao">
                            Repor {Math.max(
                              produto.estoque_minimo - produto.quantidade,
                              0,
                            )} un.
                          </small>
                        )}
                      </td>
                      {(podeMovimentarEstoque || podeEditarProdutos || podeExcluirProdutos) && <td>
                        <div className="acoes-produto">
                          {podeMovimentarEstoque && <button
                            className="entrada"
                            onClick={() => abrirMovimentacao(produto, "entrada")}
                            title="Registrar entrada"
                          >
                            <Plus size={16} />
                          </button>}
                          {podeMovimentarEstoque && <button
                            className="venda"
                            onClick={() => abrirMovimentacao(produto, "saida")}
                            title="Registrar saída"
                          >
                            <Minus size={16} />
                          </button>}
                          {podeEditarProdutos && <button
                            onClick={() => iniciarEdicao(produto)}
                            title="Editar produto"
                          >
                            <Pencil size={15} />
                          </button>}
                          {podeExcluirProdutos && <button
                            className="excluir"
                            onClick={() => removerProduto(produto)}
                            title="Excluir produto"
                          >
                            <Trash2 size={15} />
                          </button>}
                        </div>
                      </td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </section>

      {podeMovimentarEstoque && movimentacao && (
        <div className="fundo-modal">
          <form className="modal-movimentacao" onSubmit={confirmarMovimentacao}>
            <button
              type="button"
              className="fechar-modal"
              onClick={() => definirMovimentacao(null)}
            >
              <X size={20} />
            </button>
            <span>
              {movimentacao.tipo === "entrada"
                ? "ENTRADA DE ESTOQUE"
                : "SAÍDA DE ESTOQUE"}
            </span>
            <h2>{movimentacao.produto.nome}</h2>
            <p>Saldo atual: {movimentacao.produto.quantidade} unidades</p>
            <label className="campo-formulario">
              <span>Quantidade</span>
              <div>
                <input
                  type="number"
                  min="1"
                  value={quantidadeMovimento}
                  onChange={(evento) =>
                    definirQuantidadeMovimento(evento.target.value)
                  }
                  required
                  autoFocus
                />
              </div>
            </label>
            {mensagemErro && (
              <p className="mensagem-erro">{mensagemErro}</p>
            )}
            <button className="botao-principal" disabled={salvando}>
              {salvando
                ? "Registrando..."
                : movimentacao.tipo === "entrada"
                  ? "Confirmar entrada"
                  : "Confirmar saída"}
            </button>
          </form>
        </div>
      )}
    </main>
  );
}
