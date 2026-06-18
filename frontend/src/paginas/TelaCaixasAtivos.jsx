import { useEffect, useState } from "react";
import {
  Banknote,
  Clock3,
  RefreshCw,
  ShoppingCart,
  UserRound,
} from "lucide-react";

import { listarCaixasAtivos } from "../servicos/servicoApi";


const formatoMoeda = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
});


export function TelaCaixasAtivos() {
  const [caixas, definirCaixas] = useState([]);
  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState("");

  useEffect(() => {
    carregarCaixas();
    const atualizacao = window.setInterval(carregarCaixas, 30000);
    return () => window.clearInterval(atualizacao);
  }, []);

  async function carregarCaixas() {
    definirErro("");
    try {
      definirCaixas(await listarCaixasAtivos());
    } catch (falha) {
      definirErro(falha.message);
    } finally {
      definirCarregando(false);
    }
  }

  const totalVendido = caixas.reduce(
    (total, caixa) => total + Number(caixa.total_vendido),
    0,
  );

  return (
    <main className="conteudo-dashboard conteudo-caixas-ativos">
      <div className="cabecalho-pagina">
        <div>
          <span>OPERAÇÃO EM TEMPO REAL</span>
          <h1>Caixas ativos</h1>
          <p>Acompanhe os operadores que estão com expediente aberto.</p>
        </div>
        <button className="botao-atualizar-caixas" onClick={carregarCaixas}>
          <RefreshCw size={16} /> Atualizar
        </button>
      </div>

      <section className="resumo-caixas-ativos">
        <article>
          <UserRound size={21} />
          <div><span>Caixas abertos</span><strong>{caixas.length}</strong></div>
        </article>
        <article>
          <ShoppingCart size={21} />
          <div>
            <span>Vendas realizadas</span>
            <strong>
              {caixas.reduce(
                (total, caixa) => total + caixa.quantidade_vendas,
                0,
              )}
            </strong>
          </div>
        </article>
        <article>
          <Banknote size={21} />
          <div>
            <span>Total vendido</span>
            <strong>{formatoMoeda.format(totalVendido)}</strong>
          </div>
        </article>
      </section>

      <section className="lista-estoque painel-caixas-ativos">
        <div className="barra-lista">
          <div>
            <h2>Expedientes em andamento</h2>
            <small>Atualização automática a cada 30 segundos</small>
          </div>
        </div>
        {erro && <p className="mensagem-erro">{erro}</p>}
        {carregando ? (
          <p className="estado-financeiro">Carregando caixas...</p>
        ) : caixas.length === 0 ? (
          <div className="estado-vazio">
            <Clock3 size={35} />
            <h3>Nenhum caixa aberto</h3>
            <p>Os caixas aparecerão quando um operador iniciar o expediente.</p>
          </div>
        ) : (
          <div className="grade-caixas-ativos">
            {caixas.map((caixa) => (
              <article key={caixa.id}>
                <div className="cabecalho-caixa-ativo">
                  <span className="avatar-caixa">
                    {caixa.nome_usuario
                      .split(" ")
                      .map((parte) => parte[0])
                      .slice(0, 2)
                      .join("")}
                  </span>
                  <div>
                    <strong>{caixa.nome_usuario}</strong>
                    <span>{caixa.cargo_usuario} · Caixa #{caixa.id}</span>
                  </div>
                  <b>Aberto</b>
                </div>
                <div className="dados-caixa-ativo">
                  <div>
                    <span>Aberto em</span>
                    <strong>
                      {new Date(caixa.data_abertura).toLocaleString("pt-BR")}
                    </strong>
                  </div>
                  <div>
                    <span>Valor inicial</span>
                    <strong>{formatoMoeda.format(caixa.valor_inicial)}</strong>
                  </div>
                  <div>
                    <span>Total vendido</span>
                    <strong>{formatoMoeda.format(caixa.total_vendido)}</strong>
                  </div>
                  <div>
                    <span>Vendas</span>
                    <strong>{caixa.quantidade_vendas}</strong>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
