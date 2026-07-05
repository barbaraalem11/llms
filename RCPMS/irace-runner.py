#!/usr/bin/env python3
"""
irace-runner.py
─────────────────────────────────────────────────────────────────────────────
Target runner do iRace para o solver GRASP-PT/AC (grasp_pt_rcpms.py).

Contrato do iRace
─────────────────
  • argv : <configID> <instanceID> <seed> <instance> [<bound>] --param val ...
  • stdout: APENAS um número double (o custo a minimizar).
  • stderr: qualquer mensagem de diagnóstico/debug.
  • exit 0 em sucesso; exit != 0 em falha.

Modo iRace (calibração):
  ./irace-runner.py 1 1 42 instancia \
      --n_replicas 20 --mcl 500 --ptl 400 \
      --temp_init 0.1 --temp_fim 0.5 --vnd_delta 10

Modo benchmark (parâmetros calibrados via arquivo):
  ./irace-runner.py --args-file irace-output/best-configuration.args \
      instances/rcpms_all/RCPMS_Instance_166_m=10_n=200_t=11

  Saída gerada em resultados/<nome_instancia>.txt:
    instance   : RCPMS_Instance_166_m=10_n=200_t=11
    makespan   : 1234
    simulation_run makespan : 1234 bestS : [...]
    cut start set: [...]
    cut end set: [...]
    block pos set: [...]
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Sequence

_HERE   = Path(os.path.dirname(os.path.abspath(__file__)))
_SOLVER = _HERE / "grasp_pt_rcpms.py"

MAX_TIME_TUNING:    float = 60.0
MAX_TIME_BENCHMARK: float = 272.0   # tempo padrão literatura n=200


# ---------------------------------------------------------------------------
# Importação direta do solver
# ---------------------------------------------------------------------------
def _import_solver():
    import importlib.util
    spec = importlib.util.spec_from_file_location("grasp_pt_rcpms", _SOLVER)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Parser modo iRace
# ---------------------------------------------------------------------------
def _parse_irace_argv(argv: list[str]) -> tuple[str, int, dict]:
    flag_start = None
    for i, a in enumerate(argv):
        if a.startswith("--"):
            flag_start = i
            break

    if flag_start is None:
        raise ValueError("Nenhum parametro --flag encontrado.")

    fixed     = argv[:flag_start]
    flag_args = argv[flag_start:]

    if len(fixed) < 4:
        raise ValueError(f"Campos fixos insuficientes: {fixed}")

    seed     = int(fixed[2])
    instance = fixed[3]

    hyperparams: dict = {}
    it = iter(flag_args)
    for token in it:
        key   = token.lstrip("-")
        value = next(it)
        for cast in (int, float, str):
            try:
                hyperparams[key] = cast(value)
                break
            except ValueError:
                continue

    return instance, seed, hyperparams


# ---------------------------------------------------------------------------
# Parser modo benchmark (--args-file)
# ---------------------------------------------------------------------------
def _parse_args_file(args_file: str, instance: str) -> tuple[str, int, dict]:
    path = Path(args_file)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de args nao encontrado: {args_file}")

    line   = path.read_text().strip()
    tokens = line.split()

    hyperparams: dict = {}
    it = iter(tokens)
    for token in it:
        if not token.startswith("--"):
            continue
        key   = token.lstrip("-")
        value = next(it, None)
        if value is None:
            break
        for cast in (int, float, str):
            try:
                hyperparams[key] = cast(value)
                break
            except ValueError:
                continue

    return instance, 0, hyperparams


# ---------------------------------------------------------------------------
# Execução do solver — retorna (best_sol, best_ms)
# ---------------------------------------------------------------------------
def _run_solver(instance: str, seed: int, hyperparams: dict,
                max_time: float = MAX_TIME_TUNING):
    solver = _import_solver()
    inst   = solver.load_instance(instance)

    n_replicas = int(hyperparams.get("n_replicas", 20))
    mcl        = int(hyperparams.get("mcl",        500))
    ptl        = int(hyperparams.get("ptl",        400))
    temp_init  = float(hyperparams.get("temp_init", 0.1))
    temp_fim   = float(hyperparams.get("temp_fim",  0.5))
    vnd_delta  = int(hyperparams.get("vnd_delta",  10))

    best_sol, best_ms = solver.parallel_tempering(
        inst       = inst,
        n_replicas = n_replicas,
        mcl        = mcl,
        ptl        = ptl,
        temp_init  = temp_init,
        temp_fim   = temp_fim,
        vnd_delta  = vnd_delta,
        max_time   = max_time,
        max_iter   = None,
        seed       = seed,
        verbose    = False,
    )

    recomputed = solver.evaluate(best_sol, inst)
    if recomputed != best_ms:
        raise RuntimeError(
            f"Validacao interna falhou: {best_ms} != {recomputed}"
        )

    return solver, inst, best_sol, best_ms


# ---------------------------------------------------------------------------
# Salvar log completo com solução SSP
# ---------------------------------------------------------------------------
def _save_log(solver, inst: dict, best_sol, best_ms: int,
              instance_path: str, out_dir: str = "resultados") -> str:
    """
    Salva arquivo de log com:
      - nome da instância
      - makespan
      - solução SSP completa (formato compatível com mainRCPMS.cpp)
    """
    # Nome da instância sem caminho e sem extensão
    instance_name = Path(instance_path).stem

    # Criar pasta de resultados se não existir
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out_path = str(Path(out_dir) / f"{instance_name}.txt")

    # Montar solução SSP (mesma lógica do write_solution do grasp)
    tools = inst['tools']
    m     = inst['m']

    flat:      list[int]             = []
    cut_start: list[int]             = []
    cut_end:   list[int]             = []
    block_pos: list[tuple[int, int]] = []

    pos = 0
    for i in range(m):
        cut_start.append(pos)
        seq = best_sol[i]
        flat.extend(seq)
        prev_f = -1
        for k, j in enumerate(seq):
            f = tools[j]
            if f != prev_f:
                block_pos.append((pos + k, f))
                prev_f = f
        pos += len(seq)
        cut_end.append(pos)

    sol_str = "[" + ", ".join(str(j) for j in flat) + "]"
    cs_str  = "[" + ", ".join(str(c) for c in cut_start) + "]"
    ce_str  = "[" + ", ".join(str(c) for c in cut_end) + "]"
    bp_str  = "[" + ", ".join(f"{p}={f}" for p, f in block_pos) + "]"

    with open(out_path, "w") as fh:
        # Cabeçalho com instância e makespan
        fh.write(f"instance   : {instance_name}\n")
        fh.write(f"makespan   : {best_ms}\n")
        fh.write(f"\n")
        # Solução SSP no formato do validador
        fh.write(f"simulation_run makespan : {best_ms} bestS : {sol_str}\n")
        fh.write(f"cut start set: {cs_str}\n")
        fh.write(f"cut end set: {ce_str}\n")
        fh.write(f"block pos set: {bp_str}\n")

    return out_path


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    # ── Modo benchmark: --args-file <arquivo> [--seed N] <instancia> ──────
    if len(args) >= 2 and args[0] == "--args-file":
        args_file = args[1]

        # Extrair --seed opcional antes da instância
        seed_override = None
        remaining     = args[2:]
        if len(remaining) >= 2 and remaining[0] == "--seed":
            try:
                seed_override = int(remaining[1])
                remaining     = remaining[2:]
            except ValueError:
                pass

        instance = remaining[0] if remaining else None

        if instance is None:
            print("Uso: irace-runner.py --args-file <arquivo.args> [--seed N] <instancia>",
                  file=sys.stderr)
            return 1

        print(f"[benchmark] args-file={args_file} seed={seed_override} instance={instance}",
              file=sys.stderr)

        try:
            instance, seed, hyperparams = _parse_args_file(args_file, instance)
        except Exception as exc:
            print(f"ERRO: leitura do args-file falhou - {exc}", file=sys.stderr)
            return 1

        # Seed da linha de comando tem prioridade sobre o default
        if seed_override is not None:
            seed = seed_override

        print(f"[benchmark] seed={seed} params={hyperparams}", file=sys.stderr)

        try:
            solver, inst, best_sol, best_ms = _run_solver(
                instance, seed, hyperparams, max_time=MAX_TIME_BENCHMARK
            )
        except Exception as exc:
            print(f"ERRO: solver falhou - {exc}", file=sys.stderr)
            return 1

        # Salvar log completo com solução SSP
        try:
            out_path = _save_log(solver, inst, best_sol, best_ms, instance)
            print(f"[benchmark] resultado salvo em: {out_path}", file=sys.stderr)
        except Exception as exc:
            print(f"AVISO: nao foi possivel salvar log - {exc}", file=sys.stderr)

        print(f"{float(best_ms):.6f}")
        return 0

    # ── Modo iRace: configID instanceID seed instance [bound] --p v ... ───
    config_id = args[0] if args else "?"

    try:
        instance, seed, hyperparams = _parse_irace_argv(args)
    except Exception as exc:
        print(f"ERRO [{config_id}]: parse falhou - {exc}", file=sys.stderr)
        return 1

    try:
        _solver, _inst, _sol, best_ms = _run_solver(
            instance, seed, hyperparams, max_time=MAX_TIME_TUNING
        )
    except Exception as exc:
        print(f"ERRO [{config_id}]: solver falhou - {exc}", file=sys.stderr)
        return 1

    print(f"{float(best_ms):.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())