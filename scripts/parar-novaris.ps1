$ErrorActionPreference = "SilentlyContinue"
$raiz = Split-Path -Parent $PSScriptRoot
$arquivosPid = @(
    (Join-Path $raiz ".novaris-backend.pid"),
    (Join-Path $raiz ".novaris-frontend.pid")
)
$mutex = New-Object System.Threading.Mutex(
    $false,
    "Local\NovarisOneInicializador"
)
$mutexAdquirido = $false

function Encerrar-Arvore {
    param([int]$IdProcesso)

    if (Get-Process -Id $IdProcesso -ErrorAction SilentlyContinue) {
        & taskkill.exe /PID $IdProcesso /T /F 2>$null | Out-Null
    }
}

try {
    try {
        $mutexAdquirido = $mutex.WaitOne([TimeSpan]::FromSeconds(30))
    }
    catch [System.Threading.AbandonedMutexException] {
        $mutexAdquirido = $true
    }

    Write-Host "Encerrando Novaris One..."

    foreach ($arquivoPid in $arquivosPid) {
        if (-not (Test-Path $arquivoPid)) {
            continue
        }
        $conteudo = (Get-Content $arquivoPid).Trim()
        if ($conteudo -match "^\d+$") {
            Encerrar-Arvore ([int]$conteudo)
        }
        Remove-Item $arquivoPid -Force
    }

    $processosNovaris = Get-CimInstance Win32_Process |
        Where-Object {
            $_.CommandLine -like "*$raiz*" -and (
                $_.CommandLine -like "*app.main:app*8001*" -or
                $_.CommandLine -like "*http.server*5173*" -or
                $_.CommandLine -like "*vite*5173*" -or
                $_.CommandLine -like "*INICIAR_BACKEND.bat*" -or
                $_.CommandLine -like "*INICIAR_FRONTEND.bat*"
            )
        } |
        Sort-Object ParentProcessId

    foreach ($processo in $processosNovaris) {
        Encerrar-Arvore $processo.ProcessId
    }

    foreach ($porta in @(8000, 8001, 5173)) {
        $conexoes = Get-NetTCPConnection `
            -State Listen `
            -LocalPort $porta `
            -ErrorAction SilentlyContinue
        foreach ($conexao in $conexoes) {
            $processo = Get-CimInstance Win32_Process `
                -Filter "ProcessId = $($conexao.OwningProcess)"
            if ($processo.CommandLine -like "*$raiz*") {
                Encerrar-Arvore $conexao.OwningProcess
            }
        }
    }

    Start-Sleep -Seconds 1
    Write-Host "Novaris One encerrado." -ForegroundColor Green
    exit 0
}
finally {
    if ($mutexAdquirido) {
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
