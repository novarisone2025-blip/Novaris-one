import { useState } from "react";
import { ArrowRight, Eye, EyeOff, LockKeyhole, Mail } from "lucide-react";

import { usarAutenticacao } from "../contexts/ContextoAutenticacao";
import { BotaoTema } from "../componentes/BotaoTema";
import { Logotipo } from "../componentes/Logotipo";


export function TelaLogin({ abrirCadastro }) {
  const { entrar } = usarAutenticacao();
  const [email, definirEmail] = useState("");
  const [senha, definirSenha] = useState("");
  const [mostrarSenha, definirMostrarSenha] = useState(false);
  const [mensagemErro, definirMensagemErro] = useState("");
  const [enviando, definirEnviando] = useState(false);

  async function enviarFormularioLogin(evento) {
    evento.preventDefault();
    definirMensagemErro("");
    definirEnviando(true);

    try {
      await entrar(email, senha);
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirEnviando(false);
    }
  }

  return (
    <main className="pagina-autenticacao">
      <section className="painel-marca">
        <Logotipo />
        <div className="texto-marca">
          <span>GESTÃO SIMPLES. NEGÓCIOS FORTES.</span>
          <h1>Seu negócio organizado desde o primeiro dia.</h1>
          <p>
            Centralize a gestão da sua empresa em um ambiente simples,
            moderno e seguro.
          </p>
        </div>
        <div className="decoracao-marca" />
      </section>

      <section className="painel-formulario">
        <div className="tema-autenticacao"><BotaoTema /></div>
        <div className="caixa-formulario">
          <div className="titulo-formulario">
            <span>BEM-VINDO DE VOLTA</span>
            <h2>Entre na sua conta</h2>
            <p>Use seu e-mail e senha para acessar o painel.</p>
          </div>

          <form onSubmit={enviarFormularioLogin}>
            <label className="campo-formulario">
              <span>E-mail</span>
              <div>
                <Mail size={18} />
                <input
                  type="email"
                  value={email}
                  onChange={(evento) => definirEmail(evento.target.value)}
                  placeholder="seuemail@empresa.com"
                  required
                />
              </div>
            </label>

            <label className="campo-formulario">
              <span>Senha</span>
              <div>
                <LockKeyhole size={18} />
                <input
                  type={mostrarSenha ? "text" : "password"}
                  value={senha}
                  onChange={(evento) => definirSenha(evento.target.value)}
                  placeholder="Digite sua senha"
                  required
                />
                <button
                  type="button"
                  className="mostrar-senha"
                  onClick={() => definirMostrarSenha(!mostrarSenha)}
                  title={mostrarSenha ? "Ocultar senha" : "Mostrar senha"}
                >
                  {mostrarSenha ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
            </label>

            {mensagemErro && <p className="mensagem-erro">{mensagemErro}</p>}

            <button className="botao-principal" disabled={enviando}>
              {enviando ? "Entrando..." : "Entrar"}
              {!enviando && <ArrowRight size={18} />}
            </button>
          </form>

          <p className="troca-tela">
            Ainda não tem uma conta?
            <button onClick={abrirCadastro}>Criar conta grátis</button>
          </p>
        </div>
      </section>
    </main>
  );
}
