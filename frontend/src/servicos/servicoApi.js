const ENDERECO_COMPUTADOR = window.location.hostname;
const URL_API =
  import.meta.env.VITE_API_URL ||
  `http://${ENDERECO_COMPUTADOR}:8001`;

let renovacaoEmAndamento = null;
const ROTAS_SEM_RENOVACAO = new Set([
  "/auth/login",
  "/auth/register",
  "/auth/refresh",
  "/auth/logout",
]);


function salvarTokenAcesso(resposta) {
  if (resposta?.token_acesso) {
    localStorage.setItem("novaris_token", resposta.token_acesso);
  }
}


async function renovarTokenAcesso() {
  if (!renovacaoEmAndamento) {
    renovacaoEmAndamento = fetch(`${URL_API}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
    })
      .then(async (resposta) => {
        if (!resposta.ok) {
          throw new Error("Sessao expirada.");
        }
        const dados = await resposta.json();
        salvarTokenAcesso(dados);
        return dados.token_acesso;
      })
      .finally(() => {
        renovacaoEmAndamento = null;
      });
  }
  return renovacaoEmAndamento;
}


async function enviarRequisicao(caminho, opcoes = {}, permitirRenovacao = true) {
  const token = localStorage.getItem("novaris_token");
  const cabecalhos = {
    "Content-Type": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    ...opcoes.headers,
  };

  if (token) {
    cabecalhos.Authorization = `Bearer ${token}`;
  }

  const resposta = await fetch(`${URL_API}${caminho}`, {
    ...opcoes,
    headers: cabecalhos,
    credentials: "include",
  });

  if (
    resposta.status === 401 &&
    permitirRenovacao &&
    !ROTAS_SEM_RENOVACAO.has(caminho)
  ) {
    await renovarTokenAcesso();
    return enviarRequisicao(caminho, opcoes, false);
  }

  if (!resposta.ok) {
    const erro = await resposta.json().catch(() => ({}));
    throw new Error(erro.detail || "Não foi possível concluir a operação.");
  }

  if (resposta.status === 204) {
    return null;
  }

  return resposta.json();
}


async function baixarArquivo(caminho, nomeArquivo) {
  const token = localStorage.getItem("novaris_token");
  let resposta = await fetch(`${URL_API}${caminho}`, {
    credentials: "include",
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Requested-With": "XMLHttpRequest",
    },
  });
  if (resposta.status === 401) {
    const novoToken = await renovarTokenAcesso();
    resposta = await fetch(`${URL_API}${caminho}`, {
      credentials: "include",
      headers: {
        Authorization: `Bearer ${novoToken}`,
        "X-Requested-With": "XMLHttpRequest",
      },
    });
  }
  if (!resposta.ok) {
    throw new Error("Não foi possível gerar o relatório.");
  }
  const arquivo = await resposta.blob();
  const endereco = URL.createObjectURL(arquivo);
  const link = document.createElement("a");
  link.href = endereco;
  link.download = nomeArquivo;
  link.click();
  URL.revokeObjectURL(endereco);
}


export function cadastrarConta(dadosCadastro) {
  return enviarRequisicao("/auth/register", {
    method: "POST",
    body: JSON.stringify(dadosCadastro),
  });
}


export function realizarLogin(email, senha) {
  return enviarRequisicao("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, senha }),
  });
}


export function encerrarSessaoRemota() {
  return enviarRequisicao(
    "/auth/logout",
    { method: "POST" },
    false,
  );
}


export function buscarUsuarioLogado() {
  return enviarRequisicao("/auth/me");
}


export function buscarDadosDashboard() {
  return enviarRequisicao("/dashboard");
}


export function listarProdutos() {
  return enviarRequisicao("/estoque/produtos");
}


export function cadastrarProduto(dadosProduto) {
  return enviarRequisicao("/estoque/produtos", {
    method: "POST",
    body: JSON.stringify(dadosProduto),
  });
}


export function atualizarProduto(produtoId, dadosProduto) {
  return enviarRequisicao(`/estoque/produtos/${produtoId}`, {
    method: "PUT",
    body: JSON.stringify(dadosProduto),
  });
}


export function registrarMovimentacao(produtoId, tipo, quantidade) {
  return enviarRequisicao(
    `/estoque/produtos/${produtoId}/movimentacoes`,
    {
      method: "POST",
      body: JSON.stringify({ tipo, quantidade }),
    },
  );
}


export function excluirProduto(produtoId) {
  return enviarRequisicao(`/estoque/produtos/${produtoId}`, {
    method: "DELETE",
  });
}


export function listarHistoricoEstoque(filtros = {}) {
  const parametros = new URLSearchParams();
  Object.entries(filtros).forEach(([chave, valor]) => {
    if (valor) parametros.set(chave, valor);
  });
  const consulta = parametros.toString();
  return enviarRequisicao(
    `/estoque/movimentacoes${consulta ? `?${consulta}` : ""}`,
  );
}


export function listarAlertasEstoque() {
  return enviarRequisicao("/estoque/alertas");
}


export function baixarRelatorioEstoque(formato) {
  return baixarArquivo(
    `/estoque/relatorios/${formato}`,
    formato === "pdf"
      ? "relatorio-estoque.pdf"
      : "relatorio-estoque.xlsx",
  );
}


export function buscarProdutoVenda(codigoBarras) {
  return enviarRequisicao(
    `/vendas/produto/${encodeURIComponent(codigoBarras)}`,
  );
}


export function pesquisarProdutosVenda(nomeProduto) {
  const parametros = new URLSearchParams({ nome: nomeProduto });
  return enviarRequisicao(`/vendas/produtos/pesquisa?${parametros}`);
}


export function registrarVenda(
  itens,
  desconto,
  formaPagamento,
  clienteId = null,
  valorRecebido = null,
) {
  return enviarRequisicao("/vendas", {
    method: "POST",
    body: JSON.stringify({
      itens,
      desconto: Number(desconto || 0),
      forma_pagamento: formaPagamento,
      cliente_id: clienteId || null,
      valor_recebido: formaPagamento === "dinheiro"
        ? Number(valorRecebido)
        : null,
    }),
  });
}


export function baixarComprovanteVenda(vendaId) {
  return baixarArquivo(
    `/vendas/${vendaId}/comprovante`,
    `comprovante-venda-${vendaId}.pdf`,
  );
}


export function listarVendasFinanceiro() {
  return enviarRequisicao("/vendas");
}


export function listarVendasRecentes() {
  return enviarRequisicao("/vendas/recentes");
}


export function confirmarPagamentoVenda(vendaId) {
  return enviarRequisicao(`/vendas/${vendaId}/confirmar-pagamento`, {
    method: "POST",
  });
}

export function buscarStatusPagamentoVenda(vendaId) {
  return enviarRequisicao(`/vendas/${vendaId}/status-pagamento`);
}

export function cancelarVenda(vendaId, motivo) {
  return enviarRequisicao(`/vendas/${vendaId}/cancelar`, {
    method: "POST",
    body: JSON.stringify({ motivo }),
  });
}

export function detalharVendaParaDevolucao(vendaId) {
  return enviarRequisicao(`/operacoes-venda/vendas/${vendaId}`);
}

export function registrarTrocaDevolucao(vendaId, dados) {
  return enviarRequisicao(`/operacoes-venda/vendas/${vendaId}`, {
    method: "POST",
    body: JSON.stringify(dados),
  });
}

export function listarTrocasDevolucoes(vendaId = null) {
  return enviarRequisicao(
    `/operacoes-venda${vendaId ? `?venda_id=${vendaId}` : ""}`,
  );
}

export function buscarCaixaAtual() {
  return enviarRequisicao("/caixa/atual");
}

export function abrirCaixa(valorInicial) {
  return enviarRequisicao("/caixa/abrir", {
    method: "POST",
    body: JSON.stringify({ valor_inicial: Number(valorInicial) }),
  });
}

export function fecharCaixa(valorReal) {
  return enviarRequisicao("/caixa/fechar", {
    method: "POST",
    body: JSON.stringify({ valor_real: Number(valorReal) }),
  });
}

export function baixarRelatorioCaixa(caixaId) {
  return baixarArquivo(
    `/caixa/${caixaId}/relatorio`,
    `fechamento-caixa-${caixaId}.pdf`,
  );
}

export function listarCaixasAtivos() {
  return enviarRequisicao("/caixa/ativos");
}

export function registrarSangria(valor, motivo) {
  return enviarRequisicao("/caixa/sangria", {
    method: "POST",
    body: JSON.stringify({ valor: Number(valor), motivo }),
  });
}

export function registrarReforco(valor, motivo) {
  return enviarRequisicao("/caixa/reforco", {
    method: "POST",
    body: JSON.stringify({ valor: Number(valor), motivo }),
  });
}


export function buscarConfiguracaoPagamento() {
  return enviarRequisicao("/pagamentos/configuracao");
}


export function salvarConfiguracaoPagamento(dados) {
  return enviarRequisicao("/pagamentos/configuracao", {
    method: "PUT",
    body: JSON.stringify(dados),
  });
}


export function listarFornecedores() {
  return enviarRequisicao("/fornecedores");
}


export function cadastrarFornecedor(dados) {
  return enviarRequisicao("/fornecedores", {
    method: "POST",
    body: JSON.stringify(dados),
  });
}


export function atualizarFornecedor(fornecedorId, dados) {
  return enviarRequisicao(`/fornecedores/${fornecedorId}`, {
    method: "PUT",
    body: JSON.stringify(dados),
  });
}


export function excluirFornecedor(fornecedorId) {
  return enviarRequisicao(`/fornecedores/${fornecedorId}`, {
    method: "DELETE",
  });
}


function parametrosFinanceiros(filtros = {}) {
  const parametros = new URLSearchParams();
  Object.entries(filtros).forEach(([chave, valor]) => {
    if (valor) parametros.set(chave, valor);
  });
  return parametros.toString();
}


export function buscarResumoFinanceiro(filtros = {}) {
  const consulta = parametrosFinanceiros(filtros);
  return enviarRequisicao(
    `/financeiro/resumo${consulta ? `?${consulta}` : ""}`,
  );
}


export function listarFluxoCaixa(filtros = {}) {
  const consulta = parametrosFinanceiros(filtros);
  return enviarRequisicao(
    `/financeiro/fluxo-caixa${consulta ? `?${consulta}` : ""}`,
  );
}


export function registrarLancamentoFinanceiro(dados) {
  return enviarRequisicao("/financeiro/lancamentos", {
    method: "POST",
    body: JSON.stringify(dados),
  });
}


export function baixarRelatorioFinanceiro(formato, filtros = {}) {
  const consulta = parametrosFinanceiros(filtros);
  return baixarArquivo(
    `/financeiro/relatorios/${formato}${consulta ? `?${consulta}` : ""}`,
    formato === "pdf"
      ? "relatorio-financeiro.pdf"
      : "relatorio-financeiro.xlsx",
  );
}

export function buscarRelatorioAvancado(filtros = {}) {
  const consulta = parametrosFinanceiros(filtros);
  return enviarRequisicao(
    `/relatorios/vendas${consulta ? `?${consulta}` : ""}`,
  );
}

export function buscarOpcoesRelatorioAvancado() {
  return enviarRequisicao("/relatorios/opcoes");
}

export function baixarRelatorioAvancado(formato, filtros = {}) {
  const consulta = parametrosFinanceiros(filtros);
  return baixarArquivo(
    `/relatorios/vendas/${formato}${consulta ? `?${consulta}` : ""}`,
    formato === "pdf"
      ? "relatorio-avancado-vendas.pdf"
      : "relatorio-avancado-vendas.xlsx",
  );
}

export function listarBackups() {
  return enviarRequisicao("/backups");
}

export function criarBackupManual() {
  return enviarRequisicao("/backups", { method: "POST" });
}

export function baixarBackup(backupId, nomeArquivo) {
  return baixarArquivo(
    `/backups/${backupId}/download`,
    nomeArquivo || `backup-novaris-${backupId}.json.gz`,
  );
}

export function restaurarBackup(backupId) {
  return enviarRequisicao(`/backups/${backupId}/restaurar`, {
    method: "POST",
  });
}

export function listarUsuarios() {
  return enviarRequisicao("/usuarios");
}

export function buscarCatalogoPermissoes() {
  return enviarRequisicao("/usuarios/permissoes");
}

export function cadastrarUsuarioInterno(dados) {
  return enviarRequisicao("/usuarios", {
    method: "POST",
    body: JSON.stringify(dados),
  });
}

export function atualizarUsuarioInterno(usuarioId, dados) {
  return enviarRequisicao(`/usuarios/${usuarioId}`, {
    method: "PUT",
    body: JSON.stringify(dados),
  });
}

export function listarLogsAuditoria() {
  return enviarRequisicao("/usuarios/auditoria/logs");
}

export function buscarResumoOperadores() {
  return enviarRequisicao("/vendas/resumo-operadores");
}

export function buscarDesempenhoUsuarios(filtros = {}) {
  const parametros = new URLSearchParams();
  Object.entries(filtros).forEach(([chave, valor]) => {
    if (valor) parametros.set(chave, valor);
  });
  const consulta = parametros.toString();
  return enviarRequisicao(
    `/usuarios/desempenho${consulta ? `?${consulta}` : ""}`,
  );
}

export function listarClientes(busca = "") {
  const consulta = busca
    ? `?busca=${encodeURIComponent(busca)}`
    : "";
  return enviarRequisicao(`/clientes${consulta}`);
}

export function cadastrarCliente(dados) {
  return enviarRequisicao("/clientes", {
    method: "POST",
    body: JSON.stringify(dados),
  });
}

export function atualizarCliente(clienteId, dados) {
  return enviarRequisicao(`/clientes/${clienteId}`, {
    method: "PUT",
    body: JSON.stringify(dados),
  });
}

export function detalharCliente(clienteId) {
  return enviarRequisicao(`/clientes/${clienteId}`);
}

export function baixarRelatorioClientes(formato) {
  return baixarArquivo(
    `/clientes/relatorios/${formato}/arquivo`,
    formato === "pdf" ? "clientes.pdf" : "clientes.xlsx",
  );
}

export function listarSugestoesReposicao() {
  return enviarRequisicao("/compras/sugestoes");
}

export function listarPedidosCompra() {
  return enviarRequisicao("/compras");
}

export function criarPedidoCompra(dados) {
  return enviarRequisicao("/compras", {
    method: "POST",
    body: JSON.stringify(dados),
  });
}

export function alterarStatusPedidoCompra(pedidoId, status) {
  return enviarRequisicao(`/compras/${pedidoId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function listarOrcamentos(status = "") {
  return enviarRequisicao(
    `/orcamentos${status ? `?status=${encodeURIComponent(status)}` : ""}`,
  );
}

export function criarOrcamento(dados) {
  return enviarRequisicao("/orcamentos", {
    method: "POST",
    body: JSON.stringify(dados),
  });
}

export function converterOrcamento(orcamentoId, formaPagamento) {
  return enviarRequisicao(`/orcamentos/${orcamentoId}/converter`, {
    method: "POST",
    body: JSON.stringify({ forma_pagamento: formaPagamento }),
  });
}

export function cancelarOrcamento(orcamentoId) {
  return enviarRequisicao(`/orcamentos/${orcamentoId}/cancelar`, {
    method: "POST",
  });
}

export function baixarOrcamentoPdf(orcamentoId) {
  return baixarArquivo(
    `/orcamentos/${orcamentoId}/pdf`,
    `orcamento-${orcamentoId}.pdf`,
  );
}

export function buscarLinksOrcamento(orcamentoId) {
  return enviarRequisicao(`/orcamentos/${orcamentoId}/compartilhar`);
}
