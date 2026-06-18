import { useEffect, useState } from "react";
import {
  DatabaseBackup,
  Download,
  RefreshCcw,
  ShieldCheck,
} from "lucide-react";

import {
  baixarBackup,
  criarBackupManual,
  listarBackups,
  restaurarBackup,
} from "../servicos/servicoApi";


export function TelaBackupSeguranca() {
  const [backups, definirBackups] = useState([]);
  const [erro, definirErro] = useState("");
  const [mensagem, definirMensagem] = useState("");
  const [processando, definirProcessando] = useState(false);

  useEffect(() => {
    carregar();
  }, []);

  async function carregar() {
    try {
      definirBackups(await listarBackups());
    } catch (falha) {
      definirErro(falha.message);
    }
  }

  async function criar() {
    definirProcessando(true);
    try {
      await criarBackupManual();
      definirMensagem("Backup manual criado com sucesso.");
      await carregar();
    } catch (falha) {
      definirErro(falha.message);
    } finally {
      definirProcessando(false);
    }
  }

  async function restaurar(item) {
    const confirmou = window.confirm(
      `Restaurar o backup "${item.nome_arquivo}"? Um backup de seguranca sera criado antes.`,
    );
    if (!confirmou) return;
    definirProcessando(true);
    try {
      await restaurarBackup(item.id);
      definirMensagem("Backup restaurado com sucesso.");
      await carregar();
    } catch (falha) {
      definirErro(falha.message);
    } finally {
      definirProcessando(false);
    }
  }

  return (
    <main className="conteudo-dashboard conteudo-backup">
      <div className="cabecalho-pagina">
        <div><span>PROTECAO DE DADOS</span><h1>Backup e seguranca</h1><p>Snapshots isolados da sua empresa, com verificacao de integridade.</p></div>
        <button className="botao-principal botao-backup" onClick={criar} disabled={processando}><DatabaseBackup size={17} /> Criar backup agora</button>
      </div>
      <section className="aviso-backup"><ShieldCheck size={25} /><div><strong>Backup automatico diario ativo</strong><span>O arquivo completo e criptografado. Nenhuma empresa acessa os dados de outra.</span></div></section>
      {erro && <p className="mensagem-erro">{erro}</p>}
      {mensagem && <p className="mensagem-sucesso">{mensagem}</p>}
      <section className="lista-estoque">
        <div className="barra-lista"><div><h2>Copias disponiveis</h2><small>{backups.length} backup(s)</small></div></div>
        <div className="lista-backups">
          {backups.map((item) => (
            <article key={item.id}>
              <DatabaseBackup size={20} />
              <div><strong>{item.nome_arquivo}</strong><span>{item.tipo} · {new Date(item.data_criacao).toLocaleString("pt-BR")}</span><small>{Math.max(item.tamanho_bytes / 1024, 0.1).toFixed(1)} KB · SHA-256 verificado</small></div>
              <button onClick={() => baixarBackup(item.id, item.nome_arquivo)}><Download size={15} /> Baixar</button>
              <button className="restaurar" onClick={() => restaurar(item)} disabled={processando}><RefreshCcw size={15} /> Restaurar</button>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
