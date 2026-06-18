import { useState } from "react";
import { ArrowRight, Building2, LockKeyhole, Mail, Phone, User } from "lucide-react";

import { BotaoVoltar } from "../componentes/BotaoVoltar";
import { Logotipo } from "../componentes/Logotipo";
import { usarAutenticacao } from "../contexts/ContextoAutenticacao";


const formularioInicial = {
  nome_empresa: "",
  cnpj: "",
  telefone_empresa: "",
  nome_usuario: "",
  email: "",
  senha: "",
};


export function TelaCadastro({ voltarParaLogin }) {
  const { cadastrar } = usarAutenticacao();
  const [formulario, definirFormulario] = useState(formularioInicial);
  const [mensagemErro, definirMensagemErro] = useState("");
  const [enviando, definirEnviando] = useState(false);

  function atualizarCampo(evento) {
    definirFormulario({
      ...formulario,
      [evento.target.name]: evento.target.value,
    });
  }

  async function enviarFormularioCadastro(evento) {
    evento.preventDefault();
    definirMensagemErro("");
    definirEnviando(true);

    try {
      await cadastrar(formulario);
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirEnviando(false);
    }
  }

  return (
    <main className="pagina-cadastro">
      <header className="topo-cadastro">
        <Logotipo />
        <BotaoVoltar aoClicar={voltarParaLogin} />
      </header>

      <section className="conteudo-cadastro">
        <div className="introducao-cadastro">
          <span>COMECE AGORA</span>
          <h1>Crie a base da sua empresa no Novaris One.</h1>
          <p>
            O primeiro usuário será cadastrado como administrador da empresa.
          </p>
          <ol>
            <li><b>1</b> Cadastre os dados da empresa</li>
            <li><b>2</b> Crie seu acesso de administrador</li>
            <li><b>3</b> Entre no dashboard inicial</li>
          </ol>
        </div>

        <form className="formulario-cadastro" onSubmit={enviarFormularioCadastro}>
          <div className="titulo-formulario">
            <span>CADASTRO DA CONTA</span>
            <h2>Empresa e administrador</h2>
          </div>

          <div className="grade-campos">
            <CampoCadastro
              nome="nome_empresa"
              titulo="Nome da empresa"
              placeholder="Ex.: Loja Horizonte"
              valor={formulario.nome_empresa}
              aoAlterar={atualizarCampo}
              icone={Building2}
              obrigatorio
            />
            <CampoCadastro
              nome="cnpj"
              titulo="CNPJ (opcional)"
              placeholder="00.000.000/0001-00"
              valor={formulario.cnpj}
              aoAlterar={atualizarCampo}
              icone={Building2}
            />
            <CampoCadastro
              nome="telefone_empresa"
              titulo="Telefone (opcional)"
              placeholder="(11) 99999-9999"
              valor={formulario.telefone_empresa}
              aoAlterar={atualizarCampo}
              icone={Phone}
            />
            <CampoCadastro
              nome="nome_usuario"
              titulo="Seu nome"
              placeholder="Nome completo"
              valor={formulario.nome_usuario}
              aoAlterar={atualizarCampo}
              icone={User}
              obrigatorio
            />
            <CampoCadastro
              nome="email"
              titulo="Seu e-mail"
              tipo="email"
              placeholder="seuemail@empresa.com"
              valor={formulario.email}
              aoAlterar={atualizarCampo}
              icone={Mail}
              obrigatorio
            />
            <CampoCadastro
              nome="senha"
              titulo="Crie uma senha"
              tipo="password"
              placeholder="Mínimo de 8 caracteres"
              valor={formulario.senha}
              aoAlterar={atualizarCampo}
              icone={LockKeyhole}
              obrigatorio
            />
          </div>

          {mensagemErro && <p className="mensagem-erro">{mensagemErro}</p>}

          <button className="botao-principal" disabled={enviando}>
            {enviando ? "Criando conta..." : "Criar minha conta"}
            {!enviando && <ArrowRight size={18} />}
          </button>
        </form>
      </section>
    </main>
  );
}


function CampoCadastro({
  nome,
  titulo,
  tipo = "text",
  placeholder,
  valor,
  aoAlterar,
  icone: Icone,
  obrigatorio = false,
}) {
  return (
    <label className="campo-formulario">
      <span>{titulo}</span>
      <div>
        <Icone size={18} />
        <input
          name={nome}
          type={tipo}
          value={valor}
          onChange={aoAlterar}
          placeholder={placeholder}
          required={obrigatorio}
        />
      </div>
    </label>
  );
}
