import { Menu } from "lucide-react";

import { usarAutenticacao } from "../contexts/ContextoAutenticacao";
import { BotaoTema } from "./BotaoTema";


export function TopoDashboard({ abrirMenu }) {
  const { usuario } = usarAutenticacao();
  const iniciais = usuario?.nome
    ?.split(" ")
    .map((parte) => parte[0])
    .slice(0, 2)
    .join("");

  return (
    <header className="topo-dashboard">
      <button
        className="botao-menu-celular"
        onClick={abrirMenu}
        aria-label="Abrir menu"
      >
        <Menu size={22} />
      </button>

      <div className="identificacao-empresa">
        <span>EMPRESA ATUAL</span>
        <strong>{usuario?.empresa?.nome}</strong>
      </div>

      <div className="acoes-topo">
        <BotaoTema />
        <div className="perfil-usuario">
          <span>{iniciais}</span>
          <div>
            <strong>{usuario?.nome}</strong>
            <small>{usuario?.cargo || "Usuário"}</small>
          </div>
        </div>
      </div>
    </header>
  );
}
