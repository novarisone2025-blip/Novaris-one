import { useEffect, useState } from "react";
import {
  CheckCircle2,
  Copy,
  KeyRound,
  LockKeyhole,
  QrCode,
  Save,
  Webhook,
} from "lucide-react";

import {
  buscarConfiguracaoPagamento,
  salvarConfiguracaoPagamento,
} from "../servicos/servicoApi";


const formularioInicial = {
  provedor: "manual",
  chave_pix: "",
  token_api: "",
  client_id: "",
  client_secret: "",
  segredo_webhook: "",
  ativo: true,
};


export function TelaConfiguracoesPagamento() {
  const [formulario, definirFormulario] = useState(formularioInicial);
  const [configuracao, definirConfiguracao] = useState(null);
  const [mensagem, definirMensagem] = useState("");
  const [mensagemErro, definirMensagemErro] = useState("");
  const [salvando, definirSalvando] = useState(false);

  useEffect(() => {
    buscarConfiguracaoPagamento()
      .then(definirConfiguracao)
      .catch((erro) => definirMensagemErro(erro.message));
  }, []);

  function atualizarCampo(evento) {
    const { name, value, type, checked } = evento.target;
    definirFormulario({
      ...formulario,
      [name]: type === "checkbox" ? checked : value,
    });
  }

  async function salvar(evento) {
    evento.preventDefault();
    definirSalvando(true);
    definirMensagem("");
    definirMensagemErro("");
    try {
      const resposta = await salvarConfiguracaoPagamento(formulario);
      definirConfiguracao(resposta);
      definirFormulario({
        ...formularioInicial,
        provedor: resposta.provedor,
        ativo: resposta.ativo,
      });
      definirMensagem("Configuração PIX salva e protegida com sucesso.");
    } catch (erro) {
      definirMensagemErro(erro.message);
    } finally {
      definirSalvando(false);
    }
  }

  async function copiarWebhook() {
    if (!configuracao?.webhook_url) return;
    await navigator.clipboard.writeText(configuracao.webhook_url);
    definirMensagem("URL do webhook copiada.");
  }

  return (
    <main className="conteudo-dashboard conteudo-pagamentos">
      <div className="cabecalho-pagina">
        <div>
          <span>RECEBIMENTOS</span>
          <h1>Configurações de Pagamento</h1>
          <p>Vincule sua conta PIX para gerar cobranças diretamente no PDV.</p>
        </div>
      </div>

      {configuracao?.configurado && (
        <article className="resumo-configuracao-pix">
          <CheckCircle2 size={23} />
          <div>
            <strong>PIX configurado</strong>
            <span>
              {configuracao.chave_pix_mascarada} • {configuracao.provedor}
            </span>
          </div>
          <b>
            {configuracao.confirmacao_automatica
              ? "Automático"
              : configuracao.ativo ? "Manual" : "Inativo"}
          </b>
        </article>
      )}

      <section className="grade-configuracao-pix">
        <form className="formulario-produto formulario-configuracao-pix" onSubmit={salvar}>
          <div className="titulo-formulario-produto">
            <div><span>CONTA PIX</span><h2>Dados de integração</h2></div>
            <QrCode size={24} />
          </div>
          <label className="campo-formulario">
            <span>Provedor de pagamento</span>
            <div>
              <select name="provedor" value={formulario.provedor} onChange={atualizarCampo}>
                <option value="manual">PIX manual</option>
                <option value="mercado_pago">Mercado Pago</option>
                <option value="asaas">Asaas</option>
                <option value="efi">Efi / Gerencianet</option>
              </select>
            </div>
          </label>
          <label className="campo-formulario">
            <span>Chave PIX</span>
            <div><KeyRound size={17} /><input name="chave_pix" value={formulario.chave_pix} onChange={atualizarCampo} placeholder="Preencha somente para cadastrar ou alterar" /></div>
          </label>
          <label className="campo-formulario">
            <span>Token de API</span>
            <div><LockKeyhole size={17} /><input type="password" name="token_api" value={formulario.token_api} onChange={atualizarCampo} placeholder="Opcional para PIX manual" /></div>
          </label>
          <div className="duas-colunas">
            <label className="campo-formulario"><span>Client ID</span><div><input name="client_id" value={formulario.client_id} onChange={atualizarCampo} /></div></label>
            <label className="campo-formulario"><span>Client Secret</span><div><input type="password" name="client_secret" value={formulario.client_secret} onChange={atualizarCampo} /></div></label>
          </div>
          {formulario.provedor === "mercado_pago" && (
            <label className="campo-formulario">
              <span>Assinatura secreta do webhook</span>
              <div>
                <Webhook size={17} />
                <input
                  type="password"
                  name="segredo_webhook"
                  value={formulario.segredo_webhook}
                  onChange={atualizarCampo}
                  placeholder="Suas integrações > Webhooks"
                />
              </div>
            </label>
          )}
          <label className="alternador-pagamento">
            <input type="checkbox" name="ativo" checked={formulario.ativo} onChange={atualizarCampo} />
            <span>Permitir cobranças PIX no PDV</span>
          </label>
          {mensagem && <p className="mensagem-sucesso">{mensagem}</p>}
          {mensagemErro && <p className="mensagem-erro">{mensagemErro}</p>}
          <button className="botao-principal" disabled={salvando}>
            <Save size={16} /> {salvando ? "Protegendo dados..." : "Salvar configuração"}
          </button>
        </form>

        <article className="painel-seguranca-pagamento">
          <LockKeyhole size={34} />
          <span>SEGURANÇA</span>
          <h2>Credenciais protegidas</h2>
          <p>Chave PIX, token e segredos são criptografados antes de serem armazenados. A API devolve somente dados mascarados.</p>
          <div>
            <b>PIX manual</b><span>QR Code e confirmação pelo operador.</span>
            <b>Mercado Pago</b><span>Cria a cobrança pela API e confirma o pagamento por webhook.</span>
            <b>Asaas e Efi</b><span>Continuam com confirmação manual nesta versão.</span>
          </div>
          {configuracao?.webhook_url && (
            <div className="bloco-webhook-pagamento">
              <b>URL para cadastrar no provedor</b>
              <code>{configuracao.webhook_url}</code>
              <button type="button" onClick={copiarWebhook}>
                <Copy size={14} /> Copiar URL
              </button>
              {(configuracao.webhook_url.includes("localhost")
                || configuracao.webhook_url.includes("127.0.0.1")) && (
                <small>
                  Para receber notificações reais, configure PUBLIC_API_URL com
                  um endereço HTTPS público.
                </small>
              )}
            </div>
          )}
        </article>
      </section>
    </main>
  );
}
