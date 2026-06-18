param(
    [switch]$NaoAbrirNavegador
)

$ErrorActionPreference = "Stop"
$caminhoExecutaveis = $env:Path
Remove-Item Env:PATH -ErrorAction SilentlyContinue
$env:Path = $caminhoExecutaveis
$raiz = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $raiz "backend"
$frontend = Join-Path $raiz "frontend"
$arquivoPidBackend = Join-Path $raiz ".novaris-backend.pid"
$arquivoPidFrontend = Join-Path $raiz ".novaris-frontend.pid"
$urlBackend = "http://127.0.0.1:8001/health"
$urlFrontend = "http://127.0.0.1:5173"
$mutex = New-Object System.Threading.Mutex(
    $false,
    "Local\NovarisOneInicializador"
)
$mutexAdquirido = $false

function Testar-Endereco {
    param([string]$Endereco)

    try {
        $resposta = Invoke-WebRequest `
            -Uri $Endereco `
            -UseBasicParsing `
            -TimeoutSec 2
        return $resposta.StatusCode -ge 200 -and $resposta.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

function Obter-Processo {
    param([int]$IdProcesso)

    return Get-CimInstance Win32_Process `
        -Filter "ProcessId = $IdProcesso" `
        -ErrorAction SilentlyContinue
}

function Encerrar-Arvore {
    param([int]$IdProcesso)

    if (Obter-Processo $IdProcesso) {
        & taskkill.exe /PID $IdProcesso /T /F 2>$null | Out-Null
        Start-Sleep -Milliseconds 500
    }
}

function Encerrar-Pid-Salvo {
    param([string]$ArquivoPid)

    if (-not (Test-Path $ArquivoPid)) {
        return
    }

    $conteudo = (Get-Content $ArquivoPid -ErrorAction SilentlyContinue).Trim()
    if ($conteudo -match "^\d+$") {
        Encerrar-Arvore ([int]$conteudo)
    }
    Remove-Item $ArquivoPid -Force -ErrorAction SilentlyContinue
}

function Liberar-Porta-Novaris {
    param(
        [int]$Porta,
        [string]$ArquivoPid
    )

    Encerrar-Pid-Salvo $ArquivoPid
    $conexao = Get-NetTCPConnection `
        -State Listen `
        -LocalPort $Porta `
        -ErrorAction SilentlyContinue |
        Select-Object -First 1

    if (-not $conexao) {
        return
    }

    $processo = Obter-Processo $conexao.OwningProcess
    $comando = if ($processo) { $processo.CommandLine } else { "" }
    if ($comando -notlike "*$raiz*") {
        throw (
            "A porta $Porta esta sendo usada por outro programa. " +
            "Feche esse programa e tente novamente."
        )
    }

    Encerrar-Arvore $conexao.OwningProcess
}

function Aguardar-Servico {
    param(
        [string]$Nome,
        [string]$Endereco,
        [System.Diagnostics.Process]$Processo,
        [string]$ArquivoErro
    )

    for ($tentativa = 1; $tentativa -le 120; $tentativa++) {
        if (Testar-Endereco $Endereco) {
            Write-Host "$Nome pronto." -ForegroundColor Green
            return
        }
        if ($Processo.HasExited) {
            break
        }
        Start-Sleep -Milliseconds 500
    }

    $detalhes = ""
    if (Test-Path $ArquivoErro) {
        $detalhes = (
            Get-Content $ArquivoErro -Tail 18 -ErrorAction SilentlyContinue
        ) -join [Environment]::NewLine
    }
    throw "$Nome nao iniciou corretamente.`n$detalhes"
}

function Localizar-Python {
    $pythonCodex = Join-Path $env:USERPROFILE (
        ".cache\codex-runtimes\codex-primary-runtime\" +
        "dependencies\python\python.exe"
    )
    if (Test-Path $pythonCodex) {
        return $pythonCodex
    }

    $pythonSistema = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonSistema) {
        return $pythonSistema.Source
    }

    throw "Python nao foi encontrado para iniciar o frontend."
}

try {
    try {
        $mutexAdquirido = $mutex.WaitOne([TimeSpan]::FromSeconds(30))
    }
    catch [System.Threading.AbandonedMutexException] {
        $mutexAdquirido = $true
    }
    if (-not $mutexAdquirido) {
        throw "Outro inicializador do Novaris ja esta em execucao."
    }

    Write-Host "============================================"
    Write-Host "         INICIANDO NOVARIS ONE"
    Write-Host "============================================"
    Write-Host ""

    if (Testar-Endereco $urlBackend) {
        Write-Host "Backend ja esta ativo." -ForegroundColor Green
    }
    else {
        Write-Host "Iniciando backend..."
        Liberar-Porta-Novaris 8001 $arquivoPidBackend

        $uvicorn = Join-Path $backend ".deps\bin\uvicorn.exe"
        if (-not (Test-Path $uvicorn)) {
            throw "Uvicorn nao encontrado em: $uvicorn"
        }

        $logBackend = Join-Path $backend "novaris-backend.log"
        $erroBackend = Join-Path $backend "erro_backend.log"
        $env:PYTHONPATH = "$backend;$(Join-Path $backend '.deps')"
        $processoBackend = Start-Process `
            -FilePath $uvicorn `
            -ArgumentList @(
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8001"
            ) `
            -WorkingDirectory $backend `
            -WindowStyle Hidden `
            -RedirectStandardOutput $logBackend `
            -RedirectStandardError $erroBackend `
            -PassThru
        Set-Content $arquivoPidBackend $processoBackend.Id
        Aguardar-Servico `
            "Backend" `
            $urlBackend `
            $processoBackend `
            $erroBackend
    }

    if (Testar-Endereco $urlFrontend) {
        Write-Host "Frontend ja esta ativo." -ForegroundColor Green
    }
    else {
        Write-Host "Iniciando frontend..."
        Liberar-Porta-Novaris 5173 $arquivoPidFrontend

        $dist = Join-Path $frontend "dist"
        if (-not (Test-Path (Join-Path $dist "index.html"))) {
            throw (
                "Frontend compilado nao encontrado. " +
                "Execute a compilacao antes de iniciar."
            )
        }

        $python = Localizar-Python
        $logFrontend = Join-Path $frontend "novaris-frontend.log"
        $erroFrontend = Join-Path $frontend "erro_frontend.log"
        $processoFrontend = Start-Process `
            -FilePath $python `
            -ArgumentList @(
                "-m",
                "http.server",
                "5173",
                "--bind",
                "0.0.0.0",
                "--directory",
                $dist
            ) `
            -WorkingDirectory $frontend `
            -WindowStyle Hidden `
            -RedirectStandardOutput $logFrontend `
            -RedirectStandardError $erroFrontend `
            -PassThru
        Set-Content $arquivoPidFrontend $processoFrontend.Id
        Aguardar-Servico `
            "Frontend" `
            $urlFrontend `
            $processoFrontend `
            $erroFrontend
    }

    Write-Host ""
    Write-Host "Novaris One iniciado com sucesso." -ForegroundColor Green
    Write-Host "Site: http://127.0.0.1:5173"
    Write-Host "API:  http://127.0.0.1:8001/docs"
    Write-Host ""
    Write-Host (
        "Fechar a aba do navegador nao encerra o sistema. " +
        "Use PARAR_NOVARIS.bat quando desejar desligar."
    )

    if (-not $NaoAbrirNavegador) {
        Start-Process "http://127.0.0.1:5173"
    }
    exit 0
}
catch {
    Write-Host ""
    Write-Host "ERRO AO INICIAR O NOVARIS:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
finally {
    if ($mutexAdquirido) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
