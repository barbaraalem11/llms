$ErrorActionPreference = "Stop"

# ── Localizar Rscript ──────────────────────────────────────────────────────
$rscript = Get-Command Rscript -ErrorAction SilentlyContinue |
           Select-Object -First 1 -ExpandProperty Source

if ([string]::IsNullOrWhiteSpace($rscript)) {
    # Caminhos padrão no Windows — ajuste conforme sua versão do R
    $candidates = @(
        "C:\Program Files\R\R-4.4.0\bin\Rscript.exe",
        "C:\Program Files\R\R-4.3.0\bin\Rscript.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { $rscript = $c; break }
    }
}

if ([string]::IsNullOrWhiteSpace($rscript)) {
    throw "Rscript não encontrado. Instale o R ou adicione Rscript ao PATH."
}

# ── Raiz do projeto ────────────────────────────────────────────────────────
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
Set-Location -LiteralPath $projectRoot
$env:PROJECT_ROOT = $projectRoot

# ── Variáveis de ambiente padrão ───────────────────────────────────────────
# Tempo máximo por avaliação (segundos) — repassado ao target-runner
if ([string]::IsNullOrWhiteSpace($env:IRACE_RCPMS_TIME_LIMIT)) {
    $env:IRACE_RCPMS_TIME_LIMIT = "60"
}
# Paralelismo interno do solver (manter 1 quando iRace já paraleliza)
if ([string]::IsNullOrWhiteSpace($env:IRACE_RCPMS_WORKERS)) {
    $env:IRACE_RCPMS_WORKERS = "1"
}
# Recuperação automática de runs anteriores ("auto" | "fresh")
if ([string]::IsNullOrWhiteSpace($env:IRACE_RCPMS_RECOVER)) {
    $env:IRACE_RCPMS_RECOVER = "auto"
}

# ── Executar calibração ────────────────────────────────────────────────────
& $rscript (Join-Path $PSScriptRoot "run-irace.R")

if ($LASTEXITCODE -ne 0) {
    throw "iRace terminou com código de saída $LASTEXITCODE"
}
