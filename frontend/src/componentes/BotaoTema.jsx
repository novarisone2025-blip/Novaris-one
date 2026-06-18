import { Moon, Sun } from "lucide-react";

import { usarTema } from "../contexts/ContextoTema";


export function BotaoTema() {
  const { temaEscuro, alternarTema } = usarTema();

  return (
    <button
      className="botao-icone"
      onClick={alternarTema}
      title={temaEscuro ? "Usar tema claro" : "Usar tema escuro"}
      aria-label={temaEscuro ? "Usar tema claro" : "Usar tema escuro"}
    >
      {temaEscuro ? <Sun size={19} /> : <Moon size={19} />}
    </button>
  );
}
