if (!requireNamespace("irace", quietly = TRUE)) {
  stop("Package 'irace' is not installed. Run: Rscript scripts/install.R")
}

# ── Diretórios ─────────────────────────────────────────────────────────────
dir.create("irace-output", showWarnings = FALSE, recursive = TRUE)

stamp    <- format(Sys.time(), "%Y%m%d-%H%M%S")
log_path <- file.path("irace-output", paste0("irace-log-", stamp, ".txt"))
log_con  <- file(log_path, open = "wt")

L <- function(...) {
  msg <- paste0(...)
  cat(msg, "\n")
  writeLines(msg, log_con)
}

L(strrep("=", 64))
L("  CALIBRACAO iRace — GRASP-PT/AC (RCPMS)")
L("  Data/hora : ", format(Sys.time(), "%Y-%m-%d %H:%M:%S"))
L(strrep("=", 64))

# ── Ler cenário ────────────────────────────────────────────────────────────
scenario <- irace::readScenario(filename = "irace/scenario.txt")

# ── Recuperação automática ─────────────────────────────────────────────────
recover_mode    <- tolower(Sys.getenv("IRACE_RCPMS_RECOVER", "auto"))
recover_enabled <- !(recover_mode %in% c("0", "false", "fresh", "no", "none", "off"))

if (recover_enabled) {
  candidates <- list.files("irace-output", pattern = "\\.Rdata$", full.names = TRUE)
  candidates <- candidates[!grepl("recovery-input-", basename(candidates))]
  if (length(candidates) > 0) {
    info          <- file.info(candidates)
    source_file   <- candidates[which.max(info$mtime)]
    recovery_file <- file.path("irace-output",
                               paste0("recovery-input-", stamp, ".Rdata"))
    file.copy(source_file, recovery_file, overwrite = TRUE)
    scenario$recoveryFile <- recovery_file
    L("Recovering iRace from: ", recovery_file)
  } else {
    L("Nenhum .Rdata anterior; iniciando calibracao nova.")
  }
}

# ── Rodar iRace ────────────────────────────────────────────────────────────
L("")
L(strrep("-", 64))
L("  OUTPUT iRace")
L(strrep("-", 64))

irace_lines <- capture.output({
  tuned <- irace::irace(scenario = scenario)
})
for (line in irace_lines) {
  cat(line, "\n")
  writeLines(line, log_con)
}

# ── Salvar CSV ─────────────────────────────────────────────────────────────
write.csv(tuned,
          file      = "irace-output/best-configurations.csv",
          row.names = FALSE)

# ── Extrair melhor configuração ────────────────────────────────────────────
flag_by_name <- list(
  n_replicas = "--n_replicas",
  mcl        = "--mcl",
  ptl        = "--ptl",
  temp_init  = "--temp_init",
  temp_fim   = "--temp_fim",
  vnd_delta  = "--vnd_delta"
)

best <- tuned[1, , drop = FALSE]
args <- c()
for (name in names(flag_by_name)) {
  if (name %in% names(best)) {
    args <- c(args, flag_by_name[[name]], as.character(best[[name]][1]))
  }
}
args_str <- paste(args, collapse = " ")
writeLines(args_str, "irace-output/best-configuration.args")

L("")
L(strrep("=", 64))
L("  MELHOR CONFIGURACAO")
L("  ", args_str)
L("")
L("  Salvo em : irace-output/best-configuration.args")
L("  Log em   : ", log_path)
L(strrep("=", 64))

close(log_con)
cat("\nPróximo passo: bash scripts/run_benchmark.sh\n")