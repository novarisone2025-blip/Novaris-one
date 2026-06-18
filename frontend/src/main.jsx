import React from "react";
import { createRoot } from "react-dom/client";

import { Aplicacao } from "./App";
import { ProvedorAutenticacao } from "./contexts/ContextoAutenticacao";
import { ProvedorTema } from "./contexts/ContextoTema";
import "./styles/estilosGlobais.css";


createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ProvedorTema>
      <ProvedorAutenticacao>
        <Aplicacao />
      </ProvedorAutenticacao>
    </ProvedorTema>
  </React.StrictMode>,
);
