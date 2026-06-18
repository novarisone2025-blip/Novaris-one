import { useEffect, useState } from "react";
import { Building2, Pencil, Phone, Plus, Trash2, Truck, X } from "lucide-react";

import {
  atualizarFornecedor,
  cadastrarFornecedor,
  excluirFornecedor,
  listarFornecedores,
} from "../servicos/servicoApi";


const formularioVazio = {
  nome: "",
  cnpj: "",
  telefone: "",
  email: "",
  contato: "",
};


export function TelaFornecedores() {
  const [fornecedores, definirFornecedores] = useState([]);
  const [formulario, definirFormulario] = useState(formularioVazio);
  const [fornecedorEmEdicao, definirFornecedorEmEdicao] = useState(null);
  const [mensagemErro, definirMensagemErro] = useState("");
  const [salvando, definirSalvando] = useState(false);

  useEffect(() => {
    carregarFornecedores();
  }, []);

  async function carregarFornecedores() {
    try {
      definirFornecedores(await listarFornecedores());
    } catch (erro) {
      definirMensagemErro(erro.message);
    }
  }

  function atualizarCampo(evento) {
    definirFormulario({
      ...formulario,
      [evento.target.name]: evento.target.value,
    });
  }

  function editar(fornecedor) {
    definirFornecedorEmEdicao(fornecedor);
    definirFormulario({
      nome: fornecedor.nome,
      cnpj: fornecedor.cnpj || "",
      telefone: fornecedor.telefone || "",
      email: fornecedor.email || "",
      contato: fornecedor.contato || "",
    });
  }

  function cancelar() {
    definirFornecedorEmEdicao(null);
    definirFormulario(formularioVazio);
    definirMensagemErro("");
  }

  async function salvar(evento) {
    evento.preventDefault();
    definirSalvando(true);
    definirMensagemErro("");
    try {
      if (fornecedorEmEdicao) {
        await atualizarFornecedor(fornecedorEmEdicao.id, formulario);
      } else {
        await cadastrarFornecedor(formulario);
      }
      cancelar();
      await carregarFornecedores();
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function remover(fornecedor) {
    if (!window.confirm(`Excluir o fornecedor "${fornecedor.nome}"?`)) return;
    try {
      await excluirFornecedor(fornecedor.id);
      await carregarFornecedores();
    } catch (erro) {
      definirMensagemErro(erro.message);
    }
  }

  return (
    <main className="conteudo-dashboard conteudo-estoque">
      <div className="cabecalho-pagina">
        <div>
          <span>PARCEIROS COMERCIAIS</span>
          <h1>Fornecedores</h1>
          <p>Organize contatos e vincule os produtos de cada fornecedor.</p>
        </div>
      </div>

      <section className="grade-fornecedores">
        <form className="formulario-produto" onSubmit={salvar}>
          <div className="titulo-formulario-produto">
            <div>
              <span>{fornecedorEmEdicao ? "EDITAR FORNECEDOR" : "NOVO FORNECEDOR"}</span>
              <h2>{fornecedorEmEdicao ? "Atualize os dados" : "Cadastrar fornecedor"}</h2>
            </div>
            {fornecedorEmEdicao && <button type="button" onClick={cancelar}><X size={18} /></button>}
          </div>
          <label className="campo-formulario"><span>Nome da empresa</span><div><Building2 size={17} /><input name="nome" value={formulario.nome} onChange={atualizarCampo} required /></div></label>
          <label className="campo-formulario"><span>CNPJ</span><div><input name="cnpj" value={formulario.cnpj} onChange={atualizarCampo} placeholder="Opcional" /></div></label>
          <label className="campo-formulario"><span>Telefone</span><div><Phone size={17} /><input name="telefone" value={formulario.telefone} onChange={atualizarCampo} /></div></label>
          <label className="campo-formulario"><span>E-mail</span><div><input type="email" name="email" value={formulario.email} onChange={atualizarCampo} /></div></label>
          <label className="campo-formulario"><span>Pessoa de contato</span><div><input name="contato" value={formulario.contato} onChange={atualizarCampo} /></div></label>
          {mensagemErro && <p className="mensagem-erro">{mensagemErro}</p>}
          <button className="botao-principal" disabled={salvando}>
            <Plus size={16} /> {salvando ? "Salvando..." : "Salvar fornecedor"}
          </button>
        </form>

        <section className="lista-estoque lista-fornecedores">
          <div className="barra-lista"><div><h2>Fornecedores cadastrados</h2><small>{fornecedores.length} registros</small></div></div>
          {fornecedores.length === 0 ? (
            <div className="estado-vazio"><Truck size={35} /><h3>Nenhum fornecedor</h3><p>Cadastre seu primeiro parceiro comercial.</p></div>
          ) : (
            <div className="grade-cartoes-fornecedores">
              {fornecedores.map((fornecedor) => (
                <article key={fornecedor.id}>
                  <div className="icone-fornecedor"><Truck size={20} /></div>
                  <div className="dados-fornecedor">
                    <h3>{fornecedor.nome}</h3>
                    <span>{fornecedor.contato || "Contato não informado"}</span>
                    <small>{fornecedor.telefone || fornecedor.email || "Sem telefone ou e-mail"}</small>
                    <b>{fornecedor.total_produtos} produto(s) vinculado(s)</b>
                  </div>
                  <div className="acoes-produto">
                    <button onClick={() => editar(fornecedor)}><Pencil size={15} /></button>
                    <button className="excluir" onClick={() => remover(fornecedor)}><Trash2 size={15} /></button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
