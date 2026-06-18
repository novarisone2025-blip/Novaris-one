import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, History, Search } from "lucide-react";

import { listarHistoricoEstoque } from "../servicos/servicoApi";


export function TelaHistoricoEstoque() {
  const [movimentacoes, definirMovimentacoes] = useState([]);
  const [filtros, definirFiltros] = useState({
    busca: "",
    tipo: "",
    data_inicial: "",
    data_final: "",
  });
  const [carregando, definirCarregando] = useState(true);
  const [mensagemErro, definirMensagemErro] = useState("");

  useEffect(() => {
    carregarHistorico();
  }, []);

  function atualizarFiltro(evento) {
    definirFiltros({
      ...filtros,
      [evento.target.name]: evento.target.value,
    });
  }

  async function carregarHistorico(evento) {
    evento?.preventDefault();
    definirCarregando(true);
    definirMensagemErro("");
    try {
      definirMovimentacoes(await listarHistoricoEstoque(filtros));
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirCarregando(false);
    }
  }

  function limparFiltros() {
    const vazios = {
      busca: "",
      tipo: "",
      data_inicial: "",
      data_final: "",
    };
    definirFiltros(vazios);
    definirCarregando(true);
    listarHistoricoEstoque()
      .then(definirMovimentacoes)
      .catch((erro) => definirMensagemErro(erro.message))
      .finally(() => definirCarregando(false));
  }

  function formatarData(data) {
    return new Intl.DateTimeFormat("pt-BR", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(`${data}Z`));
  }

  return (
    <main className="conteudo-dashboard">
      <div className="cabecalho-pagina">
        <div>
          <span>AUDITORIA DO ESTOQUE</span>
          <h1>Histórico de Estoque</h1>
          <p>Consulte entradas, saídas e o usuário responsável.</p>
        </div>
      </div>

      <form className="filtros-historico" onSubmit={carregarHistorico}>
        <label className="campo-busca busca-historico">
          <Search size={17} />
          <input
            name="busca"
            value={filtros.busca}
            onChange={atualizarFiltro}
            placeholder="Nome ou código de barras"
          />
        </label>
        <select name="tipo" value={filtros.tipo} onChange={atualizarFiltro}>
          <option value="">Todos os tipos</option>
          <option value="entrada">Entrada</option>
          <option value="saida">Saída</option>
        </select>
        <label>
          <span>De</span>
          <input
            name="data_inicial"
            type="date"
            value={filtros.data_inicial}
            onChange={atualizarFiltro}
          />
        </label>
        <label>
          <span>Até</span>
          <input
            name="data_final"
            type="date"
            value={filtros.data_final}
            onChange={atualizarFiltro}
          />
        </label>
        <button className="botao-filtrar">Filtrar</button>
        <button type="button" className="botao-limpar" onClick={limparFiltros}>
          Limpar
        </button>
      </form>

      {mensagemErro && <p className="mensagem-erro">{mensagemErro}</p>}

      <section className="lista-estoque historico-estoque">
        <div className="barra-lista">
          <div>
            <h2>Movimentações</h2>
            <small>{movimentacoes.length} registros encontrados</small>
          </div>
        </div>

        {carregando ? (
          <p className="estado-lista">Carregando histórico...</p>
        ) : movimentacoes.length === 0 ? (
          <div className="estado-vazio">
            <History size={35} />
            <h3>Nenhuma movimentação encontrada</h3>
            <p>As entradas e saídas aparecerão aqui.</p>
          </div>
        ) : (
          <div className="tabela-responsiva">
            <table className="tabela-produtos tabela-historico">
              <thead>
                <tr>
                  <th>Produto</th>
                  <th>Tipo</th>
                  <th>Movimentado</th>
                  <th>Anterior</th>
                  <th>Atual</th>
                  <th>Data e hora</th>
                  <th>Usuário</th>
                </tr>
              </thead>
              <tbody>
                {movimentacoes.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <strong>{item.nome_produto}</strong>
                      <small>{item.codigo_barras}</small>
                    </td>
                    <td>
                      <span className={`tipo-movimento ${item.tipo}`}>
                        {item.tipo === "entrada"
                          ? <ArrowUp size={13} />
                          : <ArrowDown size={13} />}
                        {item.tipo === "entrada" ? "Entrada" : "Saída"}
                      </span>
                    </td>
                    <td>{item.quantidade} un.</td>
                    <td>{item.quantidade_anterior}</td>
                    <td><strong>{item.quantidade_atual}</strong></td>
                    <td>{formatarData(item.data_movimentacao)}</td>
                    <td>
                      {item.nome_usuario}
                      {item.origem === "venda" && <small>Venda</small>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
