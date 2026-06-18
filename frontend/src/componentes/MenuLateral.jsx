import {
  Boxes,
  DatabaseBackup,
  FileBarChart,
  History,
  Landmark,
  LayoutDashboard,
  LogOut,
  MonitorUp,
  ListChecks,
  Settings,
  ShoppingCart,
  ArrowLeftRight,
  ClipboardList,
  ContactRound,
  PackageCheck,
  Truck,
  UserCog,
} from "lucide-react";

import { usarAutenticacao } from "../contexts/ContextoAutenticacao";
import { Logotipo } from "./Logotipo";


export function MenuLateral({
  aberto,
  fecharMenu,
  paginaAtual,
  navegarPara,
}) {
  const { encerrarSessao, possuiPermissao } = usarAutenticacao();

  function sairDoSistema() {
    encerrarSessao();
    fecharMenu();
  }

  function abrirPagina(nomePagina) {
    navegarPara(nomePagina);
    fecharMenu();
  }

  const temOperacao = (
    possuiPermissao("vendas_operar")
    || possuiPermissao("orcamentos_visualizar")
    || possuiPermissao("clientes_visualizar")
    || possuiPermissao("vendas_devolver")
  );
  const temEstoque = (
    possuiPermissao("estoque_visualizar")
    || possuiPermissao("compras_visualizar")
  );
  const temGestao = (
    possuiPermissao("financeiro_visualizar")
    || possuiPermissao("relatorios_financeiros")
    || possuiPermissao("caixas_ativos_visualizar")
  );
  const temConfiguracoes = (
    possuiPermissao("usuarios_gerenciar")
    || possuiPermissao("pagamentos_gerenciar")
    || possuiPermissao("backup_gerenciar")
  );

  return (
    <aside className={`menu-lateral ${aberto ? "menu-aberto" : ""}`}>
      <div className="cabecalho-menu">
        <Logotipo />
        <button className="fechar-menu" onClick={fecharMenu}>×</button>
      </div>

      <nav>
        {possuiPermissao("dashboard_visualizar") && (
          <span className="titulo-secao-menu">Início</span>
        )}
        {possuiPermissao("dashboard_visualizar") && <button
          className={`item-menu ${paginaAtual === "dashboard" ? "ativo" : ""}`}
          onClick={() => abrirPagina("dashboard")}
        >
          <LayoutDashboard size={19} />
          Visão geral
        </button>}

        {temOperacao && <span className="titulo-secao-menu">Vendas e clientes</span>}
        {possuiPermissao("vendas_operar") && <button
          className={`item-menu ${paginaAtual === "vendas" ? "ativo" : ""}`}
          onClick={() => abrirPagina("vendas")}
        >
          <ShoppingCart size={19} />
          Vendas
        </button>}
        {possuiPermissao("vendas_operar") && <button
          className={`item-menu ${paginaAtual === "vendas-recentes" ? "ativo" : ""}`}
          onClick={() => abrirPagina("vendas-recentes")}
        >
          <ListChecks size={19} />
          Vendas recentes
        </button>}
        {possuiPermissao("orcamentos_visualizar") && <button
          className={`item-menu ${paginaAtual === "orcamentos" ? "ativo" : ""}`}
          onClick={() => abrirPagina("orcamentos")}
        >
          <ClipboardList size={19} />
          Orçamentos
        </button>}
        {possuiPermissao("clientes_visualizar") && <button
          className={`item-menu ${paginaAtual === "clientes" ? "ativo" : ""}`}
          onClick={() => abrirPagina("clientes")}
        >
          <ContactRound size={19} />
          Clientes
        </button>}
        {possuiPermissao("vendas_devolver") && <button
          className={`item-menu ${paginaAtual === "trocas" ? "ativo" : ""}`}
          onClick={() => abrirPagina("trocas")}
        >
          <ArrowLeftRight size={19} />
          Trocas e devoluções
        </button>}

        {temEstoque && <span className="titulo-secao-menu">Estoque e compras</span>}
        {possuiPermissao("estoque_visualizar") && <button
          className={`item-menu ${paginaAtual === "estoque" ? "ativo" : ""}`}
          onClick={() => abrirPagina("estoque")}
        >
          <Boxes size={19} />
          Estoque
        </button>}
        {possuiPermissao("estoque_visualizar") && <button
          className={`item-menu ${paginaAtual === "historico" ? "ativo" : ""}`}
          onClick={() => abrirPagina("historico")}
        >
          <History size={19} />
          Histórico de Estoque
        </button>}
        {possuiPermissao("compras_visualizar") && <button
          className={`item-menu ${paginaAtual === "compras" ? "ativo" : ""}`}
          onClick={() => abrirPagina("compras")}
        >
          <PackageCheck size={19} />
          Compras e reposição
        </button>}
        {possuiPermissao("estoque_visualizar") && <button
          className={`item-menu ${paginaAtual === "fornecedores" ? "ativo" : ""}`}
          onClick={() => abrirPagina("fornecedores")}
        >
          <Truck size={19} />
          Fornecedores
        </button>}

        {temGestao && <span className="titulo-secao-menu">Gestão</span>}
        {possuiPermissao("financeiro_visualizar") && <button
          className={`item-menu ${paginaAtual === "financeiro" ? "ativo" : ""}`}
          onClick={() => abrirPagina("financeiro")}
        >
          <Landmark size={19} />
          Financeiro
        </button>}
        {possuiPermissao("relatorios_financeiros") && <button
          className={`item-menu ${paginaAtual === "relatorios" ? "ativo" : ""}`}
          onClick={() => abrirPagina("relatorios")}
        >
          <FileBarChart size={19} />
          Relatórios avançados
        </button>}
        {possuiPermissao("caixas_ativos_visualizar") && <button
          className={`item-menu ${paginaAtual === "caixas-ativos" ? "ativo" : ""}`}
          onClick={() => abrirPagina("caixas-ativos")}
        >
          <MonitorUp size={19} />
          Caixas ativos
        </button>}
      </nav>

      <div className="rodape-menu">
        {temConfiguracoes && (
          <span className="titulo-secao-menu">Configurações</span>
        )}
        {possuiPermissao("usuarios_gerenciar") && <button
          className={`item-menu ${paginaAtual === "usuarios" ? "ativo" : ""}`}
          onClick={() => abrirPagina("usuarios")}
        >
          <UserCog size={18} />
          Usuários e permissões
        </button>}
        {possuiPermissao("pagamentos_gerenciar") && <button
          className={`item-menu ${paginaAtual === "pagamentos" ? "ativo" : ""}`}
          onClick={() => abrirPagina("pagamentos")}
        >
          <Settings size={18} />
          Configurações de Pagamento
        </button>}
        {possuiPermissao("backup_gerenciar") && <button
          className={`item-menu ${paginaAtual === "backup" ? "ativo" : ""}`}
          onClick={() => abrirPagina("backup")}
        >
          <DatabaseBackup size={18} />
          Backup e segurança
        </button>}
        <button className="botao-sair" onClick={sairDoSistema}>
          <LogOut size={18} />
          Sair da conta
        </button>
      </div>
    </aside>
  );
}
