#!/usr/bin/env python3
"""
=============================================================================
GRASP-PT/AC  –  Parallel Tempering com Movimentos Acoplados ao RCPMS
=============================================================================

Projeto Conceitual de Referência: GRASP-PT/AC (Revisado)
  • Soares & Carvalho (2022)  – BRKGA híbrido para o RCPMS
  • Almeida, Lima & Carvalho (2024) – Parallel Tempering para o RCPMS

Mapeamento Arquitetural → Funções
─────────────────────────────────────────────────────────────────────────────
  F  load_instance()                  Leitura da instância no formato FMS
  B  evaluate()                       Função de avaliação EXATA (réplica fiel
                                      de RCPMS.cpp::evaluate em Python)
  A  build_tool_oriented_solution()   COF – Construtor Orientado por Ferramentas
                                      (LPT intra-bloco + busca de corte natural)
  C1 move_block_transposition()       Transposição de Bloco (granularidade grossa)
  C2 move_task_between_blocks()       Troca de Tarefas Entre Blocos (média)
  C3 move_block_regrouping()          Reagrupamento de Bloco (≡ 1-Block Grouping)
  C4 select_move()                    Seleção Adaptativa por Temperatura
  D1 vnd_job_insertion()              Inserção de Lote por Ferramenta (≡ Job
                                      Insertion do BRKGA)
  D2 vnd_block_grouping()             Reagrupamento Exaustivo (≡ 1-Block Grouping)
  D3 vnd_block()                      Ciclo VND-Bloco (orquestra D1 e D2)
  E  parallel_tempering()             Motor PT: réplicas, trocas, VND periódico
  G  write_solution()                 Saída compatível com mainRCPMS.cpp

Formato de saída (compatível com mainRCPMS.cpp / RCPMS.cpp):
  simulation_run makespan : <ms> bestS : [j0, j1, ..., jN-1]
  cut start set: [c0, c1, ..., cm-1]
  cut end set: [e0, e1, ..., em-1]
  block pos set: [p0=f0, p1=f1, ...]

Uso:
  python grasp_pt_rcpms.py <instancia> [opções]

  Critérios de parada (o primeiro atingido encerra):
    --max_time  <seg>     (default 3600)
    --max_iter  <iter>    (default sem limite)

  Hiperparâmetros (passáveis por linha de comando para iRace):
    --n_replicas  κ       (default 20)
    --mcl         L       (default 500)
    --ptl         total de propostas de troca  (default 400)
    --temp_init   T_min   (default 0.1)
    --temp_fim    T_max   (default 0.5)
    --vnd_delta   pct     (default 10  → VND a cada 10% de ptl)
    --seed        semente (default 42)
    --output      arquivo (default resultado.txt)
    --verbose     0/1     (default 1)
"""

import sys
import math
import random
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed


# ─────────────────────────────────────────────────────────────────────────────
#  F.  LEITURA DA INSTÂNCIA
# ─────────────────────────────────────────────────────────────────────────────

def load_instance(path: str) -> dict:
    """
    F – Carrega uma instância RCPMS no formato FMS.

    Formato esperado:
      Linha 1 : n m l
      Linha 2 : p  (custo fixo de setup / changeTax)
      Linha 3 : f_0 f_1 ... f_{n-1}   (ferramenta de cada tarefa, 0-based)
      Linha 4 : t_0 t_1 ... t_{n-1}   (tempo de processamento)

    Retorna dict com chaves:
      n, m, l, p, tools (list[int]), times (list[int]),
      tool_groups (list[list[int]])
    """
    with open(path) as fh:
        raw = fh.read().split()
    idx = 0
    n, m, l = int(raw[idx]), int(raw[idx+1]), int(raw[idx+2]);  idx += 3
    p = int(raw[idx]);                                           idx += 1
    tools = [int(raw[idx + j]) for j in range(n)];              idx += n
    times = [int(raw[idx + j]) for j in range(n)]

    tool_groups: list[list[int]] = [[] for _ in range(l)]
    for j in range(n):
        tool_groups[tools[j]].append(j)

    return dict(n=n, m=m, l=l, p=p, tools=tools, times=times,
                tool_groups=tool_groups)


# ─────────────────────────────────────────────────────────────────────────────
#  B.  FUNÇÃO DE AVALIAÇÃO EXATA
#
#  Réplica FIEL da lógica de RCPMS.cpp::evaluate() em Python.
#  A mesma estrutura de fila FIFO, magazine, fSpamStart/End e fMachine
#  garante que o makespan calculado aqui coincide com o validador C++.
#
#  Projeto conceitual: B – Avaliação com conflitos de ferramenta e setups.
#  Complexidade: O(n · m)
# ─────────────────────────────────────────────────────────────────────────────

def evaluate(assignment: list[list[int]], inst: dict) -> int:
    """
    B – Avaliação exata do RCPMS.

    Simula o escalonamento processando jobs um a um em ordem crescente de
    tempo de término (mSpam), com:
      • fSpamStart[f] / fSpamEnd[f] : intervalo em que a ferramenta f está ocupada
      • fMachine[f]  : máquina que detém a ferramenta f
      • magazine[i]  : ferramenta no magazine da máquina i
      • Troca de ferramenta ocorre quando:
          magazine[i] != tool_do_job  OU
          (fMachine[tool] != i  E  fMachine[tool] != -1)

    Parâmetros:
        assignment : lista de m listas de jobs (0-based), em ordem de proc.
        inst       : dict retornado por load_instance().

    Retorna makespan (int) — idêntico ao valor de RCPMS.cpp::evaluate().
    """
    m_cnt  = inst['m']
    l      = inst['l']
    tools  = inst['tools']
    times  = inst['times']
    p      = inst['p']

    # Converter para representação flat (igual ao C++)
    flat:      list[int] = []
    cut_start: list[int] = []
    cut_end:   list[int] = []
    pos = 0
    for i in range(m_cnt):
        cut_start.append(pos)
        flat.extend(assignment[i])
        pos += len(assignment[i])
        cut_end.append(pos)

    mSpam      = [0] * m_cnt
    magazine   = [0] * m_cnt
    ptr        = [0] * m_cnt   # equivalente a p[m] no C++
    fSpamStart = [0] * l
    fSpamEnd   = [0] * l
    fMachine   = [-1] * l

    # Inicialização: magazine da máquina i recebe ferramenta do seu 1º job
    exec_q: list[int] = list(range(m_cnt))
    for i in range(m_cnt):
        if cut_start[i] < cut_end[i]:
            magazine[i] = tools[flat[cut_start[i]]]

    best_ms = 0

    while exec_q:
        m = exec_q.pop(0)   # FIFO — igual a std::queue

        if (cut_start[m] + ptr[m]) < cut_end[m]:
            job = flat[cut_start[m] + ptr[m]]
            f   = tools[job]
            t   = times[job]

            # Conflito de ferramenta: aguardar liberação
            if (fSpamStart[f] <= mSpam[m]) and (fSpamEnd[f] > mSpam[m]):
                mSpam[m] = fSpamEnd[f]
            else:
                fSpamStart[f] = mSpam[m]

            # Troca de ferramenta
            if (magazine[m] != f) or \
               ((fMachine[f] != m) and (fMachine[f] != -1)):
                mSpam[m] += p

            mSpam[m]    += t
            magazine[m]  = f
            fSpamEnd[f]  = mSpam[m]
            fMachine[f]  = m

        ptr[m] += 1

        if not exec_q:
            min_val = 10**18
            next_m  = -1
            for i in range(m_cnt):
                if mSpam[i] > best_ms:
                    best_ms = mSpam[i]
                if (min_val >= mSpam[i]) and \
                   ((cut_start[i] + ptr[i]) < cut_end[i]):
                    next_m  = i
                    min_val = mSpam[i]
            if next_m != -1:
                exec_q.append(next_m)

    return best_ms


# ─────────────────────────────────────────────────────────────────────────────
#  UTILITÁRIO INTERNO: identificação de blocos contíguos
# ─────────────────────────────────────────────────────────────────────────────

def _get_blocks(seq: list[int], tools: list[int]) \
        -> list[tuple[int, int, int]]:
    """
    Retorna lista de blocos contíguos de mesma ferramenta na sequência seq.
    Cada bloco: (ferramenta, início_incl, fim_excl).
    Complexidade: O(|seq|).
    """
    if not seq:
        return []
    blocks, cur_f, start = [], tools[seq[0]], 0
    for k in range(1, len(seq)):
        f = tools[seq[k]]
        if f != cur_f:
            blocks.append((cur_f, start, k))
            cur_f, start = f, k
    blocks.append((cur_f, start, len(seq)))
    return blocks


# ─────────────────────────────────────────────────────────────────────────────
#  A.  CONSTRUTOR ORIENTADO POR FERRAMENTAS (COF)
#
#  Projeto conceitual: seção 3.3.
#  Contribuições originais em relação ao PT puro (sbpo2024):
#    • LPT intra-bloco (tarefas mais pesadas primeiro dentro de cada ferramenta)
#    • Busca de ponto de corte ótimo entre fronteiras naturais de blocos
#      e posição balanceada n//m, avaliando cada candidato com evaluate()
# ─────────────────────────────────────────────────────────────────────────────

def build_tool_oriented_solution(
        inst: dict, rng: random.Random
) -> list[list[int]]:
    """
    A – Construtor Orientado por Ferramentas (COF).

    Passos:
      1. Permutação aleatória das ferramentas.
      2. Ordenar tarefas de cada ferramenta por tempo decrescente (LPT).
      3. Concatenar → sequência flat com blocos compactos por ferramenta.
      4. Buscar ponto de corte ótimo entre as fronteiras naturais de blocos
         e a posição balanceada n//m·k (k=1..m-1).

    Complexidade: O(n log n) + O(|candidatos| · n · m).
    """
    n, m, l = inst['n'], inst['m'], inst['l']
    times   = inst['times']
    tg      = inst['tool_groups']

    # Passos 1 & 2
    perm_tools = list(range(l))
    rng.shuffle(perm_tools)

    sequence:         list[int] = []
    block_boundaries: list[int] = []

    for f in perm_tools:
        grp = sorted(tg[f], key=lambda j: -times[j])   # LPT
        sequence.extend(grp)
        block_boundaries.append(len(sequence))

    # Passo 4: candidatos de corte
    candidates: set[int] = set()
    for b in block_boundaries[:-1]:   # fronteiras naturais (excl. fim)
        candidates.add(b)
    base = n // m
    for k in range(1, m):             # posições balanceadas
        c = base * k
        if 0 < c < n:
            candidates.add(c)

    best_ms   = 10**18
    best_asgn: list[list[int]] = []

    for cut in sorted(candidates):
        if cut <= 0 or cut >= n:
            continue
        # Distribuição: máquina 0 recebe [0..cut),
        # restantes recebem partes iguais do remanescente
        rem = n - cut
        per = max(1, rem // (m - 1))
        asgn: list[list[int]] = [sequence[:cut]]
        pos2 = cut
        for i in range(1, m):
            end = pos2 + per if i < m - 1 else n
            asgn.append(sequence[pos2:end])
            pos2 = end
        if any(len(a) == 0 for a in asgn):
            continue
        ms = evaluate(asgn, inst)
        if ms < best_ms:
            best_ms   = ms
            best_asgn = [list(a) for a in asgn]

    # Fallback: divisão simples caso nenhum corte válido
    if not best_asgn:
        chunk     = max(1, n // m)
        best_asgn = [sequence[i*chunk:(i+1)*chunk] for i in range(m - 1)]
        best_asgn.append(sequence[(m - 1)*chunk:])

    return best_asgn


# ───────────────────────────────────────────────────────────────────────────
#  C.  MOVIMENTOS ACOPLADOS AO RCPMS
#  Projeto conceitual: seções C1, C2, C3, C4
# ─────────────────────────────────────────────────────────────────────────────

def move_block_transposition(
        asgn: list[list[int]], inst: dict, rng: random.Random
) -> list[list[int]]:
    """
    C1 – Transposição de Bloco (TB).

    Move um bloco completo B(f, M_src) para outra máquina M_dst,
    inserindo antes do primeiro job de mesma ferramenta (ou no final).
    Preserva coesão ferramenta→bloco.  Não cria setups adicionais em M_dst
    se ela já possui jobs da mesma ferramenta.

    Granularidade GROSSA → preferível em temperaturas altas (diversificação).
    Complexidade: O(n).
    """
    m     = inst['m']
    tools = inst['tools']

    src  = rng.randint(0, m - 1)
    blks = _get_blocks(asgn[src], tools)
    if not blks:
        return asgn

    f_blk, b_s, b_e = blks[rng.randint(0, len(blks) - 1)]
    batch = asgn[src][b_s:b_e]

    dsts = [i for i in range(m) if i != src]
    if not dsts:
        return asgn
    dst = rng.choice(dsts)

    new       = [list(a) for a in asgn]
    new[src]  = new[src][:b_s] + new[src][b_e:]
    if not new[src]:          # não esvaziar máquina origem
        return asgn

    ins = len(new[dst])
    for k, j in enumerate(new[dst]):
        if tools[j] == f_blk:
            ins = k
            break
    new[dst] = new[dst][:ins] + batch + new[dst][ins:]
    return new


def move_task_between_blocks(
        asgn: list[list[int]], inst: dict, rng: random.Random
) -> list[list[int]]:
    """
    C2 – Troca de Tarefas Entre Blocos (TTB).

    Remove uma tarefa da máquina mais carregada (carga = soma de tempos)
    e insere na máquina menos carregada, respeitando agrupamento de ferramenta.
    Zero impacto no número de setups quando a máquina destino já possui
    jobs da mesma ferramenta.

    Granularidade MÉDIA → preferível em temperaturas intermediárias.
    Complexidade: O(n).
    """
    m     = inst['m']
    tools = inst['tools']
    times = inst['times']

    loads = [sum(times[j] for j in asgn[i]) for i in range(m)]
    src   = loads.index(max(loads))
    dst   = loads.index(min(loads))
    if src == dst or not asgn[src]:
        return asgn

    j_idx = rng.randint(0, len(asgn[src]) - 1)
    j     = asgn[src][j_idx]
    f     = tools[j]

    new      = [list(a) for a in asgn]
    new[src].pop(j_idx)
    if not new[src]:
        return asgn

    ins = len(new[dst])
    for k, jj in enumerate(new[dst]):
        if tools[jj] == f:
            ins = k
            break
    new[dst] = new[dst][:ins] + [j] + new[dst][ins:]
    return new


def move_block_regrouping(
        asgn: list[list[int]], inst: dict, rng: random.Random
) -> list[list[int]]:
    """
    C3 – Reagrupamento de Bloco (RB).

    Encontra uma descontinuidade de ferramenta na máquina mais carregada e
    propõe a fusão dos dois sub-blocos, eliminando uma troca de ferramenta.
    Análogo estocástico do 1-Block Grouping do BRKGA (Soares & Carvalho, 2022).

    Granularidade FINA → preferível em temperaturas baixas (intensificação).
    Complexidade: O(n).
    """
    m     = inst['m']
    tools = inst['tools']
    times = inst['times']

    loads = [sum(times[j] for j in asgn[i]) for i in range(m)]
    crit  = loads.index(max(loads))
    seq   = asgn[crit]
    if len(seq) < 3:
        return asgn

    blks  = _get_blocks(seq, tools)
    seen:  dict[int, int] = {}
    discs: list[tuple[int,int,int]] = []
    for b_idx, (f, bs, be) in enumerate(blks):
        if f in seen:
            discs.append((f, seen[f], b_idx))
        else:
            seen[f] = b_idx

    if not discs:
        return asgn

    f, prev_i, cur_i = rng.choice(discs)
    _, ps, pe = blks[prev_i]
    _, cs, ce = blks[cur_i]

    blk     = seq[ps:pe]
    new_seq = seq[:ps] + seq[pe:]
    new_cs  = cs - (pe - ps)
    new_seq = new_seq[:new_cs] + blk + new_seq[new_cs:]

    new = [list(a) for a in asgn]
    new[crit] = new_seq
    return new


def select_move(
        asgn: list[list[int]], inst: dict,
        temperature: float, t_min: float, t_max: float,
        rng: random.Random
) -> list[list[int]]:
    """
    C4 – Seleção Adaptativa de Movimento por Temperatura.

    Probabilidades como função de t_norm = (T - T_min) / (T_max - T_min):
      p_TB  = t_norm            (alta T → granularidade grossa)
      p_TTB = 1 - |2·t_norm-1| (pico na temperatura intermediária)
      p_RB  = 1 - t_norm        (baixa T → granularidade fina)

    Projeto conceitual: seção 3.4.
    """
    t_n   = (temperature - t_min) / max(t_max - t_min, 1e-9)
    p_tb  = t_n
    p_ttb = 1.0 - abs(2.0 * t_n - 1.0)
    p_rb  = 1.0 - t_n
    total = p_tb + p_ttb + p_rb + 1e-9

    r = rng.random() * total
    if r < p_tb:
        return move_block_transposition(asgn, inst, rng)
    elif r < p_tb + p_ttb:
        return move_task_between_blocks(asgn, inst, rng)
    else:
        return move_block_regrouping(asgn, inst, rng)


# ─────────────────────────────────────────────────────────────────────────────
#  D.  VND-BLOCO (INTENSIFICAÇÃO PERIÓDICA NA RÉPLICA MAIS FRIA)
#  Projeto conceitual: seção 3.5
# ─────────────────────────────────────────────────────────────────────────────

def vnd_job_insertion(
        asgn: list[list[int]], inst: dict
) -> tuple[list[list[int]], bool]:
    """
    D1 – Inserção de Lote por Ferramenta (ILF).

    Seleciona o menor lote (por soma de tempos) na máquina mais carregada
    e o move para a máquina menos carregada, inserindo antes do primeiro
    job de mesma ferramenta nessa máquina (ou no final).

    Equivalente direto ao Job Insertion do BRKGA (Soares & Carvalho, 2022).
    Complexidade: O(n²).

    Retorna (nova_solução, melhorou: bool).
    """
    m     = inst['m']
    tools = inst['tools']
    times = inst['times']

    ms_cur = evaluate(asgn, inst)
    loads  = [sum(times[j] for j in asgn[i]) for i in range(m)]
    crit   = loads.index(max(loads))
    light  = loads.index(min(loads))
    if crit == light or not asgn[crit]:
        return asgn, False

    blks = _get_blocks(asgn[crit], tools)
    if not blks:
        return asgn, False

    def lote_load(b):
        _, bs, be = b
        return sum(times[asgn[crit][k]] for k in range(bs, be))

    f_blk, b_s, b_e = min(blks, key=lote_load)
    batch = asgn[crit][b_s:b_e]

    new       = [list(a) for a in asgn]
    new[crit] = new[crit][:b_s] + new[crit][b_e:]
    if not new[crit]:
        return asgn, False

    ins = len(new[light])
    for k, jj in enumerate(new[light]):
        if tools[jj] == f_blk:
            ins = k
            break
    new[light] = new[light][:ins] + batch + new[light][ins:]

    ms_new = evaluate(new, inst)
    if ms_new < ms_cur:
        return new, True
    return asgn, False


def vnd_block_grouping(
        asgn: list[list[int]], inst: dict
) -> tuple[list[list[int]], bool]:
    """
    D2 – Reagrupamento Exaustivo (RE).

    Varre todas as ferramentas com descontinuidade na máquina mais carregada.
    Para cada descontinuidade testa os dois movimentos de fusão e aceita
    a melhor melhora (best improvement).

    Equivalente ao 1-Block Grouping do BRKGA (Soares & Carvalho, 2022).
    Complexidade: O(n³) pior caso com early termination.

    Retorna (nova_solução, melhorou: bool).
    """
    m     = inst['m']
    tools = inst['tools']
    times = inst['times']

    ms_cur = evaluate(asgn, inst)
    loads  = [sum(times[j] for j in asgn[i]) for i in range(m)]
    crit   = loads.index(max(loads))
    seq    = asgn[crit]

    blks  = _get_blocks(seq, tools)
    seen:  dict[int, int] = {}
    discs: list[tuple[int,int,int]] = []
    for b_idx, (f, bs, be) in enumerate(blks):
        if f in seen:
            discs.append((f, seen[f], b_idx))
        else:
            seen[f] = b_idx

    best_ms   = ms_cur
    best_asgn = asgn

    for f, prev_i, cur_i in discs:
        _, ps, pe = blks[prev_i]
        _, cs, ce = blks[cur_i]

        for direction in (0, 1):
            ns = list(seq)
            if direction == 0:
                blk = ns[ps:pe];  del ns[ps:pe]
                ncs = cs - (pe - ps)
                ns  = ns[:ncs] + blk + ns[ncs:]
            else:
                blk = ns[cs:ce];  del ns[cs:ce]
                ns  = ns[:pe] + blk + ns[pe:]

            cand       = [list(a) for a in asgn]
            cand[crit] = ns
            ms_c       = evaluate(cand, inst)
            if ms_c < best_ms:
                best_ms   = ms_c
                best_asgn = cand

    return best_asgn, best_ms < ms_cur


def vnd_block(
        asgn: list[list[int]], inst: dict
) -> list[list[int]]:
    """
    D3 – Ciclo VND-Bloco.

    Aplica ILF (N1) e RE (N2) em sequência, reiniciando ao encontrar melhora.
    Encerra quando nenhuma vizinhança produz melhora.

    Projeto conceitual: seção 3.5.
    """
    improved = True
    while improved:
        asgn, imp1 = vnd_job_insertion(asgn, inst)
        if imp1:
            continue
        asgn, imp2 = vnd_block_grouping(asgn, inst)
        improved   = imp2
    return asgn


# ─────────────────────────────────────────────────────────────────────────────
#  E.  PARALLEL TEMPERING  (MOTOR PRINCIPAL)
#  Projeto conceitual: seção 3.2 / 3.6 / 3.7
# ─────────────────────────────────────────────────────────────────────────────

def _temp_schedule(k: int, t_min: float, t_max: float) -> list[float]:
    """
    Distribuição exponencial de temperaturas — configuração vencedora do
    irace para o RCPMS (Almeida et al., 2024).
    T_i = T_min · (T_max/T_min)^(i/(k-1))
    """
    if k == 1:
        return [t_min]
    r = (t_max / t_min) ** (1.0 / (k - 1))
    return [t_min * (r ** i) for i in range(k)]


def _metropolis(delta: int, T: float, rng: random.Random) -> bool:
    """Aceita se delta <= 0 ou com prob exp(-delta/T)."""
    if delta <= 0:
        return True
    return rng.random() < math.exp(-delta / max(T, 1e-12))


def _run_chain(
        sol: list[list[int]], ms: int,
        T: float, t_min: float, t_max: float,
        inst: dict, mcl: int,
        rng: random.Random
) -> tuple[list[list[int]], int]:
    """
    Executa mcl passos da cadeia de Markov para uma réplica à temperatura T.
    Para cada passo: select_move → evaluate → Metropolis.
    Retorna (melhor solução encontrada, seu makespan).

    Complexidade por chamada: O(mcl · n · m).
    """
    cur_sol, cur_ms = sol, ms
    best_sol, best_ms = sol, ms

    for _ in range(mcl):
        new_sol = select_move(cur_sol, inst, T, t_min, t_max, rng)
        new_ms  = evaluate(new_sol, inst)
        if _metropolis(new_ms - cur_ms, T, rng):
            cur_sol, cur_ms = new_sol, new_ms
        if cur_ms < best_ms:
            best_ms, best_sol = cur_ms, cur_sol

    return best_sol, best_ms


def _swap_replicas(
        sols: list, mss: list, temps: list,
        i: int, j: int, rng: random.Random
) -> None:
    """
    Propõe troca de temperatura entre réplicas i e j (in-place).
    P = min(1, exp(Δβ · ΔE))  onde Δβ = 1/T_j - 1/T_i.
    """
    db = 1.0 / max(temps[j], 1e-12) - 1.0 / max(temps[i], 1e-12)
    de = mss[j] - mss[i]
    
    exponent = db * de
    if exponent > 700:
        prob = 1.0
    elif exponent < -700:
        prob = 0.0
    else:
        prob = math.exp(exponent)
    if rng.random() < min(1.0, prob):
        sols[i], sols[j] = sols[j], sols[i]
        mss[i],  mss[j]  = mss[j],  mss[i]


def _adjust_temperatures(
        temps: list[float],
        acc: list[int], tot: list[int],
        target: float = 0.23
) -> list[float]:
    """
    Ajuste dinâmico para manter taxa de aceitação em ~23%
    (critério validado pelo irace para o RCPMS, Almeida et al. 2024).
    T_min (índice 0) e T_max (índice -1) são mantidos fixos.
    """
    new_T = list(temps)
    for i in range(1, len(temps) - 1):
        if tot[i] == 0:
            continue
        rate = acc[i] / tot[i]
        if rate < target - 0.03:
            new_T[i] = min(temps[-1], new_T[i] * 1.1)
        elif rate > target + 0.03:
            new_T[i] = max(temps[0], new_T[i] * 0.9)
    return new_T


def parallel_tempering(
        inst: dict,
        n_replicas: int  = 20,
        mcl: int         = 500,
        ptl: int         = 400,
        temp_init: float = 0.1,
        temp_fim: float  = 0.5,
        vnd_delta: int   = 10,
        max_time: float  = 272.07,
        max_iter: int    = None,
        seed: int        = 42,
        verbose: bool    = True,
) -> tuple[list[list[int]], int]:
    """
    E – Motor principal GRASP-PT/AC.

    1. Inicializa κ réplicas via COF (permutações distintas por réplica).
    2. Loop principal:
       a. Cadeias de Markov em paralelo (ThreadPoolExecutor, ≤8 workers).
       b. Troca de réplicas adjacentes com alternância de paridade.
       c. VND-Bloco periódico na réplica mais fria (T_min = índice 0).
       d. Ajuste dinâmico de temperaturas a cada 50 trocas (critério 23%).
    3. Parada: max_time OU max_iter OU ptl/10 iterações sem melhora.

    Parâmetros:
        n_replicas : κ número de réplicas
        mcl        : L comprimento da cadeia de Markov por réplica por iteração
        ptl        : total de trocas alvo (critério de parada interno)
        temp_init  : T_min (réplica mais fria / índice 0)
        temp_fim   : T_max (réplica mais quente / índice κ-1)
        vnd_delta  : % de ptl entre aplicações do VND na réplica fria
        max_time   : limite de tempo (segundos)
        max_iter   : limite de iterações externas (None = sem limite)
        seed       : semente aleatória

    Retorna (melhor_assignment, melhor_makespan).
    """
    t_start  = time.time()
    rng      = random.Random(seed)
    temps    = _temp_schedule(n_replicas, temp_init, temp_fim)
    vnd_int  = max(1, ptl * vnd_delta // 100)   # intervalo em nº de trocas

    # ── Inicialização via COF ────────────────────────────────────────────────
    sols: list = []
    mss:  list[int] = []
    rep_rngs: list[random.Random] = []
    for r in range(n_replicas):
        rr = random.Random(seed + r * 1337)
        rep_rngs.append(rr)
        s  = build_tool_oriented_solution(inst, rr)
        ms = evaluate(s, inst)
        sols.append(s)
        mss.append(ms)

    best_ms  = min(mss)
    best_sol = [list(a) for a in sols[mss.index(best_ms)]]

    if verbose:
        print(f"[Init] Makespan inicial: {best_ms}", flush=True)

    acc_cnt   = [0] * n_replicas
    tot_cnt   = [0] * n_replicas
    n_swaps   = 0
    parity    = 0
    no_imp    = 0
    early_lim = 999999
    #early_lim = max(1, ptl // 10)
    iteration = 0
    n_workers = min(n_replicas, 8)

    with ThreadPoolExecutor(max_workers=n_workers) as pool:

        while True:
            # ── Critério de parada ───────────────────────────────────────────
            if time.time() - t_start >= max_time:
                if verbose:
                    print("[Parada] Tempo máximo atingido.", flush=True)
                break
            if max_iter is not None and iteration >= max_iter:
                if verbose:
                    print(f"[Parada] Limite de iterações ({max_iter}).", flush=True)
                break
            if no_imp >= early_lim:
                if verbose:
                    print(f"[Parada antecipada] {no_imp} iter. sem melhora.",
                          flush=True)
                break

            iteration += 1

            # ── a. Cadeias de Markov em paralelo ─────────────────────────────
            futs = {
                pool.submit(
                    _run_chain,
                    sols[r], mss[r], temps[r],
                    temp_init, temp_fim,
                    inst, mcl, rep_rngs[r]
                ): r
                for r in range(n_replicas)
            }
            for fut in as_completed(futs):
                r        = futs[fut]
                new_s, nm = fut.result()
                if nm < mss[r]:
                    acc_cnt[r] += 1
                tot_cnt[r] += mcl
                sols[r]     = new_s
                mss[r]      = nm

            # ── b. Trocas de temperatura (paridade alternada) ─────────────────
            for i in range(parity, n_replicas - 1, 2):
                _swap_replicas(sols, mss, temps, i, i + 1, rng)
                n_swaps += 1
            parity = 1 - parity

            # ── c. VND-Bloco periódico na réplica mais fria ───────────────────
            if n_swaps > 0 and (n_swaps % vnd_int) == 0:
                cold = 0   # T_min = índice 0
                ms_before = mss[cold]
                if verbose:
                    print(f"  [VND] troca={n_swaps:5d}  "
                          f"ms antes={ms_before}", end="", flush=True)
                sols[cold] = vnd_block(sols[cold], inst)
                mss[cold]  = evaluate(sols[cold], inst)
                if verbose:
                    print(f"  → ms depois={mss[cold]}", flush=True)

            # ── d. Ajuste dinâmico de temperaturas ───────────────────────────
            if n_swaps > 0 and (n_swaps % 50) == 0:
                temps   = _adjust_temperatures(temps, acc_cnt, tot_cnt)
                acc_cnt = [0] * n_replicas
                tot_cnt = [0] * n_replicas

            # ── Atualizar melhor global ───────────────────────────────────────
            local_best = min(range(n_replicas), key=lambda r: mss[r])
            if mss[local_best] < best_ms:
                best_ms  = mss[local_best]
                best_sol = [list(a) for a in sols[local_best]]
                no_imp   = 0
                if verbose:
                    elapsed = time.time() - t_start
                    print(f"  [Melhor] iter={iteration:4d}  "
                          f"makespan={best_ms}  t={elapsed:.1f}s", flush=True)
            else:
                no_imp += 1

    elapsed = time.time() - t_start
    if verbose:
        print(f"\n[Fim] Makespan={best_ms}  "
              f"iter={iteration}  trocas={n_swaps}  t={elapsed:.2f}s",
              flush=True)

    return best_sol, best_ms


# ─────────────────────────────────────────────────────────────────────────────
#  G.  ESCRITA DA SOLUÇÃO NO FORMATO loadResultFile()
#
#  Campos exatos que RCPMS.cpp::loadResultFile() parseia:
#    • "simulation_run" na linha → gatilho do parser
#    • "makespan : <int>"        → data.evalSol
#    • "bestS : [j0, j1, ...]"   → data.sol  (vetor flat 0-based)
#    • "cut start set: [...]"    → data.cutStart
#    • "cut end set: [...]"      → data.cutEnd
#    • "block pos set: [p=f, ...]" → data.blockPos
# ─────────────────────────────────────────────────────────────────────────────

def write_solution(
        assignment: list[list[int]],
        makespan: int,
        inst: dict,
        path: str
) -> None:
    """
    G – Escreve solução no formato lido por mainRCPMS.cpp / RCPMS.cpp.

    Gera:
      simulation_run makespan : <ms> bestS : [j0, j1, ..., jN-1]
      cut start set: [c0, c1, ..., cm-1]
      cut end set: [e0, e1, ..., em-1]
      block pos set: [p0=f0, p1=f1, ...]

    onde:
      flat     = concatenação de assignment[0..m-1]
      cutStart = posições iniciais de cada máquina no vetor flat
      cutEnd   = posições finais (exclusivas)
      blockPos = pares (posição_no_flat, ferramenta) para cada início de bloco
    """
    tools = inst['tools']
    m     = inst['m']

    flat:       list[int] = []
    cut_start:  list[int] = []
    cut_end:    list[int] = []
    block_pos:  list[tuple[int, int]] = []

    pos = 0
    for i in range(m):
        cut_start.append(pos)
        seq = assignment[i]
        flat.extend(seq)

        # Registrar início de cada bloco contíguo de ferramenta
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

    with open(path, "w") as fh:
        fh.write(f"simulation_run makespan : {makespan} bestS : {sol_str}\n")
        fh.write(f"cut start set: {cs_str}\n")
        fh.write(f"cut end set: {ce_str}\n")
        fh.write(f"block pos set: {bp_str}\n")

# ─────────────────────────────────────────────────────────────────────────────
#  INTERFACE DE LINHA DE COMANDO
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="GRASP-PT/AC – Parallel Tempering acoplado ao RCPMS",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    ap.add_argument("instance",
                    help="Caminho para o arquivo de instância RCPMS")
    ap.add_argument("--output",       default="resultado.txt",
                    help="Arquivo de saída compatível com mainRCPMS.cpp")
    # Critérios de parada
    ap.add_argument("--max_time",     type=float, default=327.04,
                    help="Limite de tempo em segundos")
    ap.add_argument("--max_iter",     type=int,   default=None,
                    help="Limite de iterações externas (None = sem limite)")
    # Hiperparâmetros (ajustáveis via iRace)
    ap.add_argument("--n_replicas",   type=int,   default=20,
                    help="κ: número de réplicas")
    ap.add_argument("--mcl",          type=int,   default=500,
                    help="L: comprimento da cadeia de Markov por réplica")
    ap.add_argument("--ptl",          type=int,   default=400,
                    help="Total alvo de propostas de troca de temperatura")
    ap.add_argument("--temp_init",    type=float, default=0.1,
                    help="T_min: temperatura mínima (réplica mais fria)")
    ap.add_argument("--temp_fim",     type=float, default=0.5,
                    help="T_max: temperatura máxima (réplica mais quente)")
    ap.add_argument("--vnd_delta",    type=int,   default=10,
                    help="%% de ptl entre aplicações periódicas do VND")
    ap.add_argument("--seed",         type=int,   default=42,
                    help="Semente aleatória para reprodutibilidade")
    ap.add_argument("--verbose",      type=int,   default=1,
                    help="Nível de verbosidade (0=silencioso, 1=detalhado)")
    return ap.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
#  PONTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    # F – Carregar instância
    inst = load_instance(args.instance)
    if args.verbose:
        print(f"Instância: n={inst['n']}  m={inst['m']}  "
              f"l={inst['l']}  p={inst['p']}", flush=True)

    # E – Executar GRASP-PT/AC
    best_sol, best_ms = parallel_tempering(
        inst       = inst,
        n_replicas = args.n_replicas,
        mcl        = args.mcl,
        ptl        = args.ptl,
        temp_init  = args.temp_init,
        temp_fim   = args.temp_fim,
        vnd_delta  = args.vnd_delta,
        max_time   = args.max_time,
        max_iter   = args.max_iter,
        seed       = args.seed,
        verbose    = bool(args.verbose),
    )

    # G – Escrever resultado
    write_solution(best_sol, best_ms, inst, args.output)

    # Exibir sumário
    print(f"\n{'='*54}")
    print(f"  MELHOR MAKESPAN ENCONTRADO : {best_ms}")
    print(f"  Resultado salvo em         : {args.output}")
    print(f"{'='*54}")

    # Distribuição por máquina
    if args.verbose:
        tools = inst['tools']
        times = inst['times']
        print("\nDistribuição por máquina:")
        for i, seq in enumerate(best_sol):
            load   = sum(times[j] for j in seq)
            n_f    = len({tools[j] for j in seq})
            blks   = _get_blocks(seq, tools)
            print(f"  M{i+1:02d}: {len(seq):3d} tarefas | "
                  f"carga={load:5d} | {n_f:2d} ferramentas | "
                  f"{len(blks):2d} blocos")


if __name__ == "__main__":
    main()
