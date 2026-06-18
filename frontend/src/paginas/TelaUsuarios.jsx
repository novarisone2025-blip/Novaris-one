import { useEffect, useState } from "react";
import {
  Activity,
  ArrowDownUp,
  BarChart3,
  Landmark,
  Save,
  ShieldCheck,
  ShoppingCart,
  UserPlus,
  Users,
} from "lucide-react";

import {
  atualizarUsuarioInterno,
  buscarCatalogoPermissoes,
  buscarDesempenhoUsuarios,
  cadastrarUsuarioInterno,
  listarLogsAuditoria,
  listarUsuarios,
} from "../servicos/servicoApi";


const vazio = {
  nome: "",
  email: "",
  senha: "",
  cargo: "Caixa",
  permissoes: [],
  ativo: true,
};
const moeda = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});


export function TelaUsuarios() {
  const [usuarios, definirUsuarios] = useState([]);
  const [catalogo, definirCatalogo] = useState({
    permissoes: {},
    predefinicoes_cargos: {},
  });
  const [operadores, definirOperadores] = useState([]);
  const [logs, definirLogs] = useState([]);
  const [formulario, definirFormulario] = useState(vazio);
  const [editando, definirEditando] = useState(null);
  const [aba, definirAba] = useState("usuarios");
  const [erro, definirErro] = useState("");
  const [mensagem, definirMensagem] = useState("");
  const hoje = new Date().toISOString().slice(0, 10);
  const [filtrosDesempenho, definirFiltrosDesempenho] = useState({
    usuario_id: "",
    data_inicial: `${hoje.slice(0, 8)}01`,
    data_final: hoje,
  });

  useEffect(() => {
    carregar();
  }, []);

  async function carregar() {
    try {
      const [equipe, permissoes, desempenho, auditoria] = await Promise.all([
        listarUsuarios(),
        buscarCatalogoPermissoes(),
        buscarDesempenhoUsuarios(filtrosDesempenho),
        listarLogsAuditoria(),
      ]);
      definirUsuarios(equipe);
      definirCatalogo(permissoes);
      definirOperadores(desempenho);
      definirLogs(auditoria);
      definirFormulario((atual) => atual.permissoes.length ? atual : {
        ...atual,
        permissoes: permissoes.predefinicoes_cargos.Caixa || [],
      });
    } catch (falha) {
      definirErro(falha.message);
    }
  }

  async function filtrarDesempenho() {
    try {
      definirErro("");
      definirOperadores(
        await buscarDesempenhoUsuarios(filtrosDesempenho),
      );
    } catch (falha) {
      definirErro(falha.message);
    }
  }

  const totaisDesempenho = operadores.reduce(
    (total, item) => ({
      vendas: total.vendas + item.quantidade_vendas,
      faturamento: total.faturamento + Number(item.total_vendido),
      estoque: total.estoque + item.movimentacoes_estoque,
      financeiro: total.financeiro + item.lancamentos_financeiros,
    }),
    { vendas: 0, faturamento: 0, estoque: 0, financeiro: 0 },
  );

  function alterarCargo(cargo) {
    definirFormulario({
      ...formulario,
      cargo,
      permissoes: catalogo.predefinicoes_cargos[cargo] || [],
    });
  }

  function alternarPermissao(permissao) {
    definirFormulario({
      ...formulario,
      permissoes: formulario.permissoes.includes(permissao)
        ? formulario.permissoes.filter((item) => item !== permissao)
        : [...formulario.permissoes, permissao],
    });
  }

  function permissaoBloqueada(permissao) {
    return (
      (formulario.cargo === "Caixa" && permissao === "estoque_gerenciar")
      || (
        formulario.cargo !== "Administrador"
        && permissao === "caixas_ativos_visualizar"
      )
    );
  }

  function editar(usuario) {
    definirEditando(usuario.id);
    definirFormulario({
      nome: usuario.nome,
      email: usuario.email,
      senha: "",
      cargo: usuario.cargo,
      permissoes: usuario.permissoes,
      ativo: usuario.ativo,
    });
  }

  function limpar() {
    definirEditando(null);
    definirFormulario({
      ...vazio,
      permissoes: catalogo.predefinicoes_cargos.Caixa || [],
    });
  }

  async function salvar(evento) {
    evento.preventDefault();
    definirErro("");
    definirMensagem("");
    try {
      if (editando) {
        await atualizarUsuarioInterno(editando, {
          nome: formulario.nome,
          email: formulario.email,
          cargo: formulario.cargo,
          permissoes: formulario.permissoes,
          ativo: formulario.ativo,
          nova_senha: formulario.senha || null,
        });
        definirMensagem("Usuário atualizado com sucesso.");
      } else {
        await cadastrarUsuarioInterno(formulario);
        definirMensagem("Usuário interno criado com sucesso.");
      }
      limpar();
      await carregar();
    } catch (falha) {
      definirErro(falha.message);
    }
  }

  return (
    <main className="conteudo-dashboard conteudo-usuarios">
      <div className="cabecalho-pagina">
        <div>
          <span>EQUIPE E SEGURANÇA</span>
          <h1>Usuários e permissões</h1>
          <p>Gerencie acessos, resultados individuais e atividades da equipe.</p>
        </div>
      </div>

      <div className="abas-configuracao">
        <button className={aba === "usuarios" ? "ativo" : ""} onClick={() => definirAba("usuarios")}><Users size={16} /> Equipe</button>
        <button className={aba === "operadores" ? "ativo" : ""} onClick={() => definirAba("operadores")}><BarChart3 size={16} /> Desempenho dos caixas</button>
        <button className={aba === "auditoria" ? "ativo" : ""} onClick={() => definirAba("auditoria")}><Activity size={16} /> Auditoria</button>
      </div>

      {aba === "usuarios" && (
        <section className="grade-usuarios">
          <form className="formulario-produto formulario-usuario" onSubmit={salvar}>
            <div className="titulo-formulario-produto">
              <div><span>ACESSO INTERNO</span><h2>{editando ? "Editar usuário" : "Novo usuário"}</h2></div>
              {editando ? <ShieldCheck size={24} /> : <UserPlus size={24} />}
            </div>
            <label className="campo-formulario"><span>Nome</span><div><input value={formulario.nome} onChange={(e) => definirFormulario({...formulario, nome: e.target.value})} required /></div></label>
            <label className="campo-formulario"><span>E-mail de login</span><div><input type="email" value={formulario.email} onChange={(e) => definirFormulario({...formulario, email: e.target.value})} required /></div></label>
            <label className="campo-formulario"><span>{editando ? "Nova senha (opcional)" : "Senha"}</span><div><input type="password" minLength="8" value={formulario.senha} onChange={(e) => definirFormulario({...formulario, senha: e.target.value})} required={!editando} /></div></label>
            <label className="campo-formulario"><span>Cargo / função</span><div><select value={formulario.cargo} onChange={(e) => alterarCargo(e.target.value)}>{["Caixa", "Gerente", "Estoquista", "Administrador"].map((cargo) => <option key={cargo}>{cargo}</option>)}</select></div></label>
            <div className="lista-permissoes">
              <strong>Permissões específicas</strong>
              {Object.entries(catalogo.permissoes).map(([chave, nome]) => (
                <label key={chave}>
                  <input
                    type="checkbox"
                    checked={formulario.permissoes.includes(chave)}
                    disabled={permissaoBloqueada(chave)}
                    onChange={() => alternarPermissao(chave)}
                  />
                  <span>{nome}</span>
                </label>
              ))}
            </div>
            {editando && <label className="alternador-pagamento"><input type="checkbox" checked={formulario.ativo} onChange={(e) => definirFormulario({...formulario, ativo: e.target.checked})} /><span>Usuário ativo</span></label>}
            {erro && <p className="mensagem-erro">{erro}</p>}
            {mensagem && <p className="mensagem-sucesso">{mensagem}</p>}
            <button className="botao-principal"><Save size={16} /> {editando ? "Salvar alterações" : "Criar usuário"}</button>
            {editando && <button type="button" className="botao-cancelar-usuario" onClick={limpar}>Cancelar edição</button>}
          </form>

          <section className="lista-estoque lista-usuarios">
            <div className="barra-lista"><div><h2>Equipe da empresa</h2><small>{usuarios.length} usuário(s)</small></div></div>
            <div className="grade-cartoes-usuarios">
              {usuarios.map((usuario) => (
                <article key={usuario.id} className={!usuario.ativo ? "usuario-inativo" : ""}>
                  <div className="avatar-equipe">{usuario.nome.split(" ").map((parte) => parte[0]).slice(0, 2).join("")}</div>
                  <div><strong>{usuario.nome}</strong><span>{usuario.email}</span><small>{usuario.cargo} · {usuario.permissoes.length} permissões</small></div>
                  <div className="estado-usuario"><b>{usuario.ativo ? "Ativo" : "Inativo"}</b><button onClick={() => editar(usuario)}>Editar</button></div>
                </article>
              ))}
            </div>
          </section>
        </section>
      )}

      {aba === "operadores" && (
        <div className="area-desempenho-usuarios">
          <section className="filtros-desempenho">
            <label><span>Usuário</span><select value={filtrosDesempenho.usuario_id} onChange={(e) => definirFiltrosDesempenho({...filtrosDesempenho, usuario_id: e.target.value})}><option value="">Todos os usuários</option>{usuarios.map((usuario) => <option key={usuario.id} value={usuario.id}>{usuario.nome} · {usuario.cargo}</option>)}</select></label>
            <label><span>De</span><input type="date" value={filtrosDesempenho.data_inicial} onChange={(e) => definirFiltrosDesempenho({...filtrosDesempenho, data_inicial: e.target.value})} /></label>
            <label><span>Até</span><input type="date" value={filtrosDesempenho.data_final} onChange={(e) => definirFiltrosDesempenho({...filtrosDesempenho, data_final: e.target.value})} /></label>
            <button onClick={filtrarDesempenho}>Atualizar relatório</button>
          </section>

          <section className="resumo-desempenho">
            <article><ShoppingCart size={20} /><div><span>Vendas realizadas</span><strong>{totaisDesempenho.vendas}</strong><small>{moeda.format(totaisDesempenho.faturamento)}</small></div></article>
            <article><ArrowDownUp size={20} /><div><span>Movimentações de estoque</span><strong>{totaisDesempenho.estoque}</strong><small>Entradas e saídas</small></div></article>
            <article><Landmark size={20} /><div><span>Lançamentos financeiros</span><strong>{totaisDesempenho.financeiro}</strong><small>Registros manuais</small></div></article>
          </section>

          <section className="lista-estoque painel-operadores">
            <div className="barra-lista"><div><h2>Desempenho por usuário</h2><small>Vendas, estoque e financeiro no período selecionado</small></div></div>
            <div className="tabela-responsiva"><table className="tabela-produtos tabela-operadores-completa"><thead><tr><th>Usuário</th><th>Vendas</th><th>Faturamento</th><th>Estoque</th><th>Unidades</th><th>Financeiro</th><th>Entradas / Saídas</th><th>Última venda</th></tr></thead><tbody>
              {operadores.map((item) => <tr key={item.usuario_id}><td><strong>{item.nome_usuario}</strong><small>{item.cargo_usuario} · {item.ativo ? "Ativo" : "Inativo"}</small></td><td>{item.quantidade_vendas}<small>Descontos: {moeda.format(item.total_descontos)}</small></td><td><strong>{moeda.format(item.total_vendido)}</strong><div className="formas-usuario">{Object.entries(item.formas_pagamento).map(([forma, total]) => <span className="etiqueta-pagamento" key={forma}>{forma}: {moeda.format(total)}</span>)}</div></td><td>{item.movimentacoes_estoque}<small>{item.entradas_estoque} entrada(s) · {item.saidas_estoque} saída(s)</small></td><td><span className="valor-entrada">+{item.unidades_entrada}</span><span className="valor-saida">-{item.unidades_saida}</span></td><td>{item.lancamentos_financeiros}<small>Lançamentos manuais</small></td><td><span className="valor-entrada">{moeda.format(item.entradas_financeiras)}</span><span className="valor-saida">{moeda.format(item.saidas_financeiras)}</span></td><td>{item.ultima_venda ? new Date(item.ultima_venda).toLocaleString("pt-BR") : "Sem vendas"}</td></tr>)}
              {operadores.length === 0 && <tr><td colSpan="8">Nenhum usuário encontrado no período.</td></tr>}
            </tbody></table></div>
          </section>
        </div>
      )}

      {aba === "auditoria" && (
        <section className="lista-estoque painel-auditoria">
          <div className="barra-lista"><div><h2>Registro de atividades</h2><small>Últimas ações realizadas na empresa</small></div></div>
          <div className="lista-logs">
            {logs.map((log) => <article key={log.id}><div className="icone-log"><Activity size={18} /></div><div><strong>{log.nome_usuario}</strong><span>{log.acao.replaceAll("_", " ")} · {log.entidade}{log.entidade_id ? ` #${log.entidade_id}` : ""}</span><small>{log.cargo_usuario} · {new Date(log.data_acao).toLocaleString("pt-BR")}</small></div></article>)}
          </div>
        </section>
      )}
    </main>
  );
}
