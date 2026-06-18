import { createContext, useContext, useEffect, useState } from "react";


const ContextoTema = createContext(null);


export function ProvedorTema({ children }) {
  const [temaEscuro, definirTemaEscuro] = useState(
    () => localStorage.getItem("novaris_tema") === "escuro",
  );

  useEffect(() => {
    const nomeTema = temaEscuro ? "escuro" : "claro";
    document.documentElement.dataset.tema = nomeTema;
    localStorage.setItem("novaris_tema", nomeTema);
  }, [temaEscuro]);

  function alternarTema() {
    definirTemaEscuro((temaAtual) => !temaAtual);
  }

  return (
    <ContextoTema.Provider value={{ temaEscuro, alternarTema }}>
      {children}
    </ContextoTema.Provider>
  );
}


export function usarTema() {
  return useContext(ContextoTema);
}
