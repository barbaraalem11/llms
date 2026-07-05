if (!requireNamespace("irace", quietly = TRUE)) {
  stop("Package 'irace' is not installed. Run: Rscript scripts/install.R")
}

# Garante que irace-output/ existe na raiz do projeto
dir.create("irace-output", showWarnings = FALSE, recursive = TRUE)

# Lê o scenario a partir da pasta irace/ (relativo à raiz do projeto)
scenario <- irace::readScenario(filename = "irace/scenario.txt")

# ── Recuperação automática de runs anteriores ──────────────────────────────
recover_mode    <- tolower(Sys.getenv("IRACE_RCPMS_RECOVER", "auto"))
recover_enabled <- !(recover_mode %in% c("0", "false", "fresh", "no", "none", "off"))

if (recover_enabled) {
  candidates <- list.files(
    "irace-output",
    pattern    = "\\.Rdata$",
    full.names = TRUE
  )
  candidates <- candidates[!grepl("recovery-input-", basename(candidates))]

  if (length(candidates) > 0) {
    info          <- file.info(candidates)
    source_file   <- candidates[which.max(info$mtime)]
    stamp         <- format(Sys.time(), "%Y%m%d-%H%M%S")
    recovery_file <- file.path("irace-output",
                               paste0("recovery-input-", stamp, ".Rdata"))
    file.copy(source_file, recovery_file, overwrite = TRUE)
    scenario$recoveryFile <- recovery_file
    cat("Recovering iRace from:", recovery_file, "\n")
    cat("New iRace logFile    :", scenario$logFile, "\n")
  } else {
    cat("No previous iRace .Rdata found; starting a fresh calibration.\n")
  }
}

# ── Executar calibração ────────────────────────────────────────────────────
tuned <- irace::irace(scenario = scenario)

# ── Salvar resultados ──────────────────────────────────────────────────────
dir.create("irace-output", showWarnings = FALSE, recursive = TRUE)
write.csv(tuned,
          file      = "irace-output/best-configurations.csv",
          row.names = FALSE)

# Mapeamento: nome da coluna (iRace) → flag CLI do grasp_pt_rcpms.py
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

writeLines(paste(args, collapse = " "),
           "irace-output/best-configuration.args")
cat("Best GRASP-PT args:", paste(args, collapse = " "), "\n")
