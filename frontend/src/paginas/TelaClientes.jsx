import { useEffect, useState } from "react";
import {
  FileSpreadsheet,
  FileText,
  Mail,
  MapPin,
  Pencil,
  Phone,
  Search,
  UserPlus,
  Users,
  X,
} from "lucide-react";

import {
  atualizarCliente,
  baixarRelatorioClientes,
  cadastrarCliente,
  detalharCliente,
  listarClientes,
} from "../servicos/servicoApi";


const vazio = {
  nome: "", documento: "", telefone: "", whatsapp: "",
  email: "", endereco: "", observacoes: "", ativo: true,
};
const formatoMoeda = new Intl.NumberFormat("pt-BR", {
  style: "currency", currency: "BRL",
});


export function TelaClientes() {
  const [clientes, definirClientes] = useState([]);
  const [formulario, definirFormulario] = useState(vazio);
  const [edicao, definirEdicao] = useState(null);
  const [detalhe, definirDetalhe] = useState(null);
  const [busca, definirBusca] = useState("");
  const [mensagemErro, definirMensagemErro] = useState("");
  const [salvando, definirSalvando] = useState(false);

  useEffect(() => { carregar(); }, []);

  async function carregar(termo = busca) {
    try {
      definirClientes(await listarClientes(termo));
    } catch (erro) {
      definirMensagemErro(erro.message);
    }
  }

  function alterarCampo(evento) {
    definirFormulario({
      ...formulario,
      [evento.target.name]: evento.target.value,
    });
  }

  function editar(cliente) {
    definirEdicao(cliente);
    definirFormulario({
      nome: cliente.nome,
      documento: cliente.documento || "",
      telefone: cliente.telefone || "",
      whatsapp: cliente.whatsapp || "",
      email: cliente.email || "",
      endereco: cliente.endereco || "",
      observacoes: cliente.observacoes || "",
      ativo: cliente.ativo,
    });
  }

  function limpar() {
    definirEdicao(null);
    definirFormulario(vazio);
  }

  async function salvar(evento) {
    evento.preventDefault();
    definirSalvando(true);
    definirMensagemErro("");
    try {
      if (edicao) await atualizarCliente(edicao.id, formulario);
      else await cadastrarCliente(formulario);
      limpar();
      await carregar("");
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function abrirDetalhe(cliente) {
    try {
      definirDetalhe(await detalharCliente(cliente.id));
    } catch (erro) {
      definirMensagemErro(erro.message);
    }
  }

  return (
    <main className="conteudo-dashboard conteudo-comercial">
      <div className="cabecalho-pagina">
        <div><span>RELACIONAMENTO COM CLIENTES</span><h1>Clientes</h1><p>Conheça o histórico e o valor de cada relacionamento.</p></div>
        <div className="acoes-relatorio">
          <button onClick={() => baixarRelatorioClientes("pdf")}><FileText size={16} /> PDF</button>
          <button onClick={() => baixarRelatorioClientes("excel")}><FileSpreadsheet size={16} /> Excel</button>
        </div>
      </div>

      <section className="grade-clientes">
        <form className="formulario-produto formulario-cliente" onSubmit={salvar}>
          <div className="titulo-formulario-produto">
            <div><span>{edicao ? "EDITAR CLIENTE" : "NOVO CLIENTE"}</span><h2>{edicao ? "Atualizar cadastro" : "Cadastrar cliente"}</h2></div>
            {edicao && <button type="button" onClick={limpar}><X size={18} /></button>}
          </div>
          <label className="campo-formulario"><span>Nome</span><div><Users size={16} /><input name="nome" value={formulario.nome} onChange={alterarCampo} required /></div></label>
          <div className="duas-colunas">
            <label className="campo-formulario"><span>CPF/CNPJ</span><div><input name="documento" value={formulario.documento} onChange={alterarCampo} /></div></label>
            <label className="campo-formulario"><span>Telefone</span><div><Phone size={15} /><input name="telefone" value={formulario.telefone} onChange={alterarCampo} /></div></label>
          </div>
          <div className="duas-colunas">
            <label className="campo-formulario"><span>WhatsApp</span><div><input name="whatsapp" value={formulario.whatsapp} onChange={alterarCampo} /></div></label>
            <label className="campo-formulario"><span>E-mail</span><div><Mail size={15} /><input type="email" name="email" value={formulario.email} onChange={alterarCampo} /></div></label>
          </div>
          <label className="campo-formulario"><span>Endereço</span><div><MapPin size={15} /><input name="endereco" value={formulario.endereco} onChange={alterarCampo} /></div></label>
          <label className="campo-formulario"><span>Observações</span><div><textarea name="observacoes" value={formulario.observacoes} onChange={alterarCampo} /></div></label>
          {mensagemErro && <p className="mensagem-erro">{mensagemErro}</p>}
          <button className="botao-principal" disabled={salvando}><UserPlus size={16} /> {salvando ? "Salvando..." : "Salvar cliente"}</button>
        </form>

        <section className="lista-estoque">
          <div className="barra-lista">
            <div><h2>Base de clientes</h2><small>{clientes.length} clientes encontrados</small></div>
            <form className="campo-busca" onSubmit={(evento) => { evento.preventDefault(); carregar(); }}>
              <Search size={16} /><input value={busca} onChange={(evento) => definirBusca(evento.target.value)} placeholder="Nome, documento ou telefone" />
            </form>
          </div>
          <div className="grade-cartoes-clientes">
            {clientes.map((cliente) => (
              <article key={cliente.id} onClick={() => abrirDetalhe(cliente)}>
                <div className="avatar-cliente">{cliente.nome.slice(0, 2).toUpperCase()}</div>
                <div><h3>{cliente.nome}</h3><span>{cliente.whatsapp || cliente.telefone || cliente.email || "Sem contato"}</span><small>{cliente.quantidade_compras} compra(s) · Ticket {formatoMoeda.format(cliente.ticket_medio)}</small></div>
                <div className="valor-cliente"><span>Total gasto</span><strong>{formatoMoeda.format(cliente.total_gasto)}</strong><button onClick={(evento) => { evento.stopPropagation(); editar(cliente); }}><Pencil size={14} /> Editar</button></div>
              </article>
            ))}
            {clientes.length === 0 && <div className="estado-vazio"><Users /><h3>Nenhum cliente</h3><p>Cadastre o primeiro cliente da empresa.</p></div>}
          </div>
        </section>
      </section>

      {detalhe && (
        <div className="fundo-modal">
          <article className="modal-cliente">
            <button className="fechar-modal" onClick={() => definirDetalhe(null)}><X /></button>
            <span>VISÃO 360° DO CLIENTE</span><h2>{detalhe.nome}</h2><p>{detalhe.documento || "Documento não informado"} · {detalhe.whatsapp || detalhe.telefone || "Sem telefone"}</p>
            <div className="metricas-cliente">
              <div><span>Total gasto</span><strong>{formatoMoeda.format(detalhe.total_gasto)}</strong></div>
              <div><span>Compras</span><strong>{detalhe.quantidade_compras}</strong></div>
              <div><span>Ticket médio</span><strong>{formatoMoeda.format(detalhe.ticket_medio)}</strong></div>
            </div>
            <h3>Produtos mais comprados</h3>
            <div className="lista-preferencias">
              {detalhe.produtos_mais_comprados.map((item) => <div key={item.codigo_barras}><span>{item.nome}</span><strong>{item.quantidade} un.</strong></div>)}
              {!detalhe.produtos_mais_comprados.length && <small>As preferências aparecerão após as vendas.</small>}
            </div>
            <h3>Histórico de compras</h3>
            <div className="lista-preferencias">
              {detalhe.historico_compras.map((item) => <div key={item.venda_id}><span>Venda #{item.venda_id} · {new Date(item.data_venda).toLocaleDateString("pt-BR")}</span><strong>{formatoMoeda.format(item.valor_total)}</strong></div>)}
            </div>
          </article>
        </div>
      )}
    </main>
  );
}
