"""
patterns/comportamental.py

Padrão COMPORTAMENTAL (heurístico, sem ML)
Implementa a lógica narrativa validada:

Ideia-base:
- A mesa paga regiões por "capítulos" (núcleos vivos).
- Âncoras surgem por repetição recente e/ou reativação histórica.
- Depois que um capítulo paga 1 faltante forte, pode abrir "capítulo 2"
  em um cluster compacto imediatamente na sequência.
- Faltantes nascem de:
    (a) vizinhos reais das âncoras repetidas;
    (b) espelhos das âncoras (quando existir);
    (c) buracos internos do cluster vivo;
    (d) eco posicional por duplicação (ex.: 14,14 / 34,34 etc.);
- Priorização sempre do capítulo vivo (últimas janelas).

Saída:
- candidatos: ranking final
- scores: dict normalizado 0-1
- metadata: debug do capítulo, âncoras, clusters, dívidas etc.
"""

from __future__ import annotations

from typing import List, Dict, Any, Tuple, Optional
from collections import Counter, defaultdict

from .base import BasePattern, PatternResult

# Helpers do seu projeto (ajuste o import se necessário)
from helpers.utils.filters import get_neighbords, get_mirror


class ComportamentalPattern(BasePattern):
    """
    history: lista com o MAIS RECENTE no índice 0
    """

    def analyze(self, history: List[int]) -> PatternResult:
        # ---------------------------
        # 0) validação mínima
        # ---------------------------
        min_size = self.get_config_value("min_size", 80)
        if not self.validate_history(history, min_size=min_size):
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={
                    "error": "Histórico insuficiente para Comportamental",
                    "history_size": len(history) if history else 0,
                    "min_size": min_size,
                },
                pattern_name=self.name,
            )

        max_history = self.get_config_value("max_history", 200)
        chapter_window = self.get_config_value("chapter_window", 12)     # capítulo vivo
        anchor_window = self.get_config_value("anchor_window", 40)       # suporte
        min_anchor_repeats = self.get_config_value("min_anchor_repeats", 2)
        max_anchors = self.get_config_value("max_anchors", 4)
        top_candidates = self.get_config_value("top_candidates", 18)

        # pesos heurísticos (ajuste fino via config)
        W_ANCHOR_REPEAT   = self.get_config_value("w_anchor_repeat", 1.0)
        W_ANCHOR_SUPPORT  = self.get_config_value("w_anchor_support", 0.6)
        W_NEIGHBOR        = self.get_config_value("w_neighbor", 0.9)
        W_MIRROR          = self.get_config_value("w_mirror", 0.7)
        W_MIRROR_NEIGHBOR = self.get_config_value("w_mirror_neighbor", 0.5)
        W_HOLE            = self.get_config_value("w_hole", 0.8)
        W_DUPLICATION_ECO = self.get_config_value("w_duplication_eco", 0.9)
        W_RECENT_PENALTY  = self.get_config_value("w_recent_penalty", 0.55)

        # histórico cronológico (antigo -> recente)
        hist = list(reversed(history[:max_history]))
        n = len(hist)

        chapter = hist[-chapter_window:] if n > chapter_window else hist
        support = hist[-anchor_window:] if n > anchor_window else hist

        # ---------------------------
        # 1) detectar âncoras
        # ---------------------------
        count_chapter = Counter(chapter)
        count_support = Counter(support)

        # âncoras do capítulo vivo (repetiram)
        anchors_live = [
            num for num, c in count_chapter.most_common()
            if c >= min_anchor_repeats
        ][:max_anchors]

        # âncoras de suporte (mesmo se não repetiu no vivo)
        anchors_support = [
            num for num, c in count_support.most_common()
            if c >= min_anchor_repeats
        ][:max_anchors]

        # união preservando ordem de força
        anchors: List[int] = []
        for a in anchors_live + anchors_support:
            if a not in anchors:
                anchors.append(a)

        # se nenhum anchor, fallback: cluster do capítulo
        if not anchors:
            fallback_scores = {num: float(c) for num, c in count_chapter.items()}
            fallback_scores = self.normalize_scores(fallback_scores)
            ordenados = sorted(fallback_scores.items(), key=lambda x: x[1], reverse=True)[:top_candidates]
            return PatternResult(
                candidatos=[num for num, _ in ordenados],
                scores={num: sc for num, sc in ordenados},
                metadata={
                    "mode": "fallback_chapter_frequency",
                    "chapter": chapter,
                    "chapter_size": len(chapter),
                },
                pattern_name=self.name,
            )

        # ---------------------------
        # 2) construir cluster vivo por proximidade narrativa
        #     (não usa sequência numérica; usa a roda do helper)
        # ---------------------------
        # Cluster vivo inicial = âncoras + vizinhos reais delas (capítulo vivo)
        cluster_vivo: set[int] = set()
        for a in anchors:
            cluster_vivo.add(a)
            for nb in get_neighbords(a):
                cluster_vivo.add(nb)

        # ---------------------------
        # 3) pontuar dívidas/faltantes
        # ---------------------------
        scores: Dict[int, float] = defaultdict(float)

        # 3.1 âncoras repetidas no capítulo vivo
        for a in anchors:
            rep_live = count_chapter.get(a, 0)
            rep_sup  = count_support.get(a, 0)

            if rep_live > 0:
                scores[a] += W_ANCHOR_REPEAT * rep_live
            if rep_sup > rep_live:
                scores[a] += W_ANCHOR_SUPPORT * (rep_sup - rep_live)

            # vizinhos do anchor
            for nb in get_neighbords(a):
                scores[nb] += W_NEIGHBOR * max(1, rep_live)

            # espelhos do anchor + vizinhos do espelho
            mirrors = get_mirror(a)
            if isinstance(mirrors, int):
                mirrors = [mirrors]
            for m in mirrors:
                if m is None:
                    continue
                scores[m] += W_MIRROR * max(1, rep_live)
                for mnb in get_neighbords(m):
                    scores[mnb] += W_MIRROR_NEIGHBOR * max(1, rep_live)

        # 3.2 buracos internos do cluster vivo
        # buraco = número que é vizinho real de 2+ números do cluster, mas não apareceu no capítulo
        set_chapter = set(chapter)
        neighbor_hits: Dict[int, int] = defaultdict(int)
        for cnum in cluster_vivo:
            for nb in get_neighbords(cnum):
                neighbor_hits[nb] += 1

        for num, hits in neighbor_hits.items():
            if hits >= 2 and num not in set_chapter:
                scores[num] += W_HOLE * hits

        # 3.3 eco por duplicação imediata (ex.: 14,14 / 34,34 etc.)
        # se duplicou no capítulo, aumenta pressão nos vizinhos reais desse duplicado
        for num, c in count_chapter.items():
            if c >= 2:
                for nb in get_neighbords(num):
                    scores[nb] += W_DUPLICATION_ECO * c

        # 3.4 penalizar ultra recentes (últimos 2-3)
        recent_block = chapter[-3:]
        for r in recent_block:
            if r in scores:
                scores[r] *= W_RECENT_PENALTY

        # remover último número (não apostar nele como candidato)
        last_num = chapter[-1]
        if last_num in scores:
            scores.pop(last_num, None)

        # ---------------------------
        # 4) normalizar e rankear
        # ---------------------------
        scores_norm = self.normalize_scores(dict(scores))
        ordenados = sorted(scores_norm.items(), key=lambda x: x[1], reverse=True)[:top_candidates]

        candidatos = [num for num, _ in ordenados]
        scores_final = {num: sc for num, sc in ordenados}

        metadata = {
            "mode": "comportamental",
            "anchors": anchors,
            "anchors_live": anchors_live,
            "anchors_support": anchors_support,
            "chapter": chapter,
            "support_window": support[:],
            "cluster_vivo": sorted(list(cluster_vivo)),
            "recent_block": recent_block,
            "chapter_size": len(chapter),
            "history_size": len(hist),
        }

        return PatternResult(
            candidatos=candidatos,
            scores=scores_final,
            metadata=metadata,
            pattern_name=self.name,
        )


def create_comportamental_pattern(**kwargs) -> ComportamentalPattern:
    return ComportamentalPattern(config=kwargs)