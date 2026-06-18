import { useState } from "react";

import { usarAutenticacao } from "./contexts/ContextoAutenticacao";
import { TelaCadastro } from "./paginas/TelaCadastro";
import { TelaDashboard } from "./paginas/TelaDashboard";
import { TelaLogin } from "./paginas/TelaLogin";


export function Aplicacao() {
  const { usuario, carregandoSessao } = usarAutenticacao();
  const [telaPublica, definirTelaPublica] = useState("login");

  if (carregandoSessao) {
    return <div className="tela-carregamento">Carregando Novaris One...</div>;
  }

  if (usuario) {
    return <TelaDashboard />;
  }

  if (telaPublica === "cadastro") {
    return (
      <TelaCadastro
        voltarParaLogin={() => definirTelaPublica("login")}
      />
    );
  }

  return (
    <TelaLogin
      abrirCadastro={() => definirTelaPublica("cadastro")}
    />
  );
}
