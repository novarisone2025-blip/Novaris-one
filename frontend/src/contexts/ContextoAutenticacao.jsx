import { createContext, useContext, useEffect, useState } from "react";

import {
  buscarUsuarioLogado,
  cadastrarConta,
  encerrarSessaoRemota,
  realizarLogin,
} from "../servicos/servicoApi";


const ContextoAutenticacao = createContext(null);


export function ProvedorAutenticacao({ children }) {
  const [usuario, definirUsuario] = useState(null);
  const [carregandoSessao, definirCarregandoSessao] = useState(true);

  useEffect(() => {
    restaurarSessao();
  }, []);

  async function restaurarSessao() {
    try {
      const dadosUsuario = await buscarUsuarioLogado();
      definirUsuario(dadosUsuario);
    } catch {
      encerrarSessao();
    } finally {
      definirCarregandoSessao(false);
    }
  }

  async function entrar(email, senha) {
    const resposta = await realizarLogin(email, senha);
    localStorage.setItem("novaris_token", resposta.token_acesso);
    const dadosUsuario = await buscarUsuarioLogado();
    definirUsuario(dadosUsuario);
  }

  async function cadastrar(dadosCadastro) {
    const resposta = await cadastrarConta(dadosCadastro);
    localStorage.setItem("novaris_token", resposta.token_acesso);
    const dadosUsuario = await buscarUsuarioLogado();
    definirUsuario(dadosUsuario);
  }

  function encerrarSessao() {
    localStorage.removeItem("novaris_token");
    definirUsuario(null);
    encerrarSessaoRemota().catch(() => {});
  }

  function possuiPermissao(permissao) {
    return Boolean(usuario?.permissoes?.includes(permissao));
  }

  return (
    <ContextoAutenticacao.Provider
      value={{
        usuario,
        carregandoSessao,
        entrar,
        cadastrar,
        encerrarSessao,
        possuiPermissao,
      }}
    >
      {children}
    </ContextoAutenticacao.Provider>
  );
}


export function usarAutenticacao() {
  return useContext(ContextoAutenticacao);
}
