from typing import Dict, List, Any, Tuple
from collections import defaultdict
import math

# usa teus helpers
from helpers.utils.filters import get_neighbords, get_mirror
from helpers.utils.roda import POSICAO_RODA  # dict num->pos na roda (0..36)

def _rank_dict(scores: Dict[int, float]) -> Dict[int, int]:
    """Retorna rank 1..N baseado em score desc."""
    ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return {n: i+1 for i, (n, _) in enumerate(ordenados)}

def build_meta_features(
    history: List[int],  # mais recente no índice 0
    resultado_estelar,
    resultado_chain,
    resultado_temporal,
    resultado_quente,
    top_k_ref: int = 12,
    max_pool: int = 37
) -> Tuple[List[int], Dict[int, Dict[str, float]]]:
    """
    Retorna:
      pool: lista de números candidatos (subconjunto ou 0..36)
      feats: dict {num: {feature: value}}
    """
    # ---- extrair scores normalizados dos padrões ----
    s_est = dict(resultado_estelar.scores or {})
    s_chain = dict(resultado_chain.scores or {})
    s_temp = dict(resultado_temporal.scores or {})
    s_hot = dict(resultado_quente.scores or {})

    r_est = _rank_dict(s_est)
    r_chain = _rank_dict(s_chain)
    r_temp = _rank_dict(s_temp)
    r_hot = _rank_dict(s_hot)

    # ---- pool base = união dos candidatos + equivalências dos tops ----
    pool_set = set()
    for d in (s_est, s_chain, s_temp, s_hot):
        pool_set |= set(d.keys())

    # tops brutos do ensemble (união não compactada)
    union_scores = defaultdict(float)
    for n, sc in s_est.items(): union_scores[n] += sc
    for n, sc in s_chain.items(): union_scores[n] += sc
    for n, sc in s_temp.items(): union_scores[n] += sc
    for n, sc in s_hot.items(): union_scores[n] += sc

    top_union = [n for n, _ in sorted(union_scores.items(), key=lambda x:x[1], reverse=True)[:top_k_ref]]

    # adiciona vizinhos/espelhos dos tops
    for n in top_union:
        pool_set.add(n)
        for v in get_neighbords(n):
            pool_set.add(v)
        mirrors = get_mirror(n)
        if isinstance(mirrors, int): mirrors = [mirrors]
        for m in mirrors:
            pool_set.add(m)
            for vm in get_neighbords(m):
                pool_set.add(vm)

    # fallback: se pool ficar vazio, usa 0..36
    if not pool_set:
        pool_set = set(range(37))

    pool = sorted(list(pool_set))[:max_pool]

    # ---- features por número ----
    feats = {}
    last_seen = {}
    for idx, num in enumerate(history):
        if num not in last_seen:
            last_seen[num] = idx  # 0 = saiu agora

    # cluster simples por proximidade na roda usando top_union como núcleo
    # (bem leve, só pra feature)
    top_pos = [POSICAO_RODA[n] for n in top_union if n in POSICAO_RODA]

    for num in pool:
        f = {}

        # presença / score / rank
        f["p_in_estelar"] = 1.0 if num in s_est else 0.0
        f["p_in_chain"]   = 1.0 if num in s_chain else 0.0
        f["p_in_temporal"]= 1.0 if num in s_temp else 0.0
        f["p_in_quente"]  = 1.0 if num in s_hot else 0.0

        f["p_score_estelar"]  = float(s_est.get(num, 0.0))
        f["p_score_chain"]    = float(s_chain.get(num, 0.0))
        f["p_score_temporal"] = float(s_temp.get(num, 0.0))
        f["p_score_quente"]   = float(s_hot.get(num, 0.0))

        f["p_rank_estelar"]  = float(r_est.get(num, 0))
        f["p_rank_chain"]    = float(r_chain.get(num, 0))
        f["p_rank_temporal"] = float(r_temp.get(num, 0))
        f["p_rank_quente"]   = float(r_hot.get(num, 0))

        # consenso
        consenso = f["p_in_estelar"] + f["p_in_chain"] + f["p_in_temporal"] + f["p_in_quente"]
        f["consenso_count"] = consenso
        f["flag_consenso_2p"] = 1.0 if consenso >= 2 else 0.0
        f["flag_consenso_3p"] = 1.0 if consenso >= 3 else 0.0
        f["flag_consenso_4p"] = 1.0 if consenso >= 4 else 0.0

        # equivalência com top_union
        f["flag_vizinho_de_top"] = 1.0 if any(num in get_neighbords(t) for t in top_union) else 0.0

        mirrors_top = set()
        for t in top_union:
            mir = get_mirror(t)
            if isinstance(mir, int): mir = [mir]
            mirrors_top |= set(mir)
        f["flag_espelho_de_top"] = 1.0 if num in mirrors_top else 0.0

        # recência / gap
        f["gap_desde_ultima_ocorrencia"] = float(last_seen.get(num, 999))

        # dist na roda até núcleo (mínima)
        if num in POSICAO_RODA and top_pos:
            p = POSICAO_RODA[num]
            dmin = min((abs(p - tp) % 37) for tp in top_pos)
            f["dist_roda_para_cluster_principal"] = float(dmin)
        else:
            f["dist_roda_para_cluster_principal"] = 99.0

        feats[num] = f

    return pool, feats