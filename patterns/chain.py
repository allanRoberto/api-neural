"""
patterns/chain.py

Implementação do padrão Chain em cima da BasePattern.

Ideia geral:
- Identifica âncoras (números que se repetem no "capítulo" mais recente).
- Para cada âncora, analisa as puxadas históricas nos próximos giros
  (janela primária e janela estendida).
- Agrega essas puxadas em um score por número, favorecendo:
    - quem aparece com frequência como puxada de âncoras fortes;
    - quem ainda não "pagou" no capítulo recente (dívida).
- Penaliza números ultra recentes e monta um ranking final.
"""

from typing import List, Dict, Any, Tuple
from collections import Counter

from .base import BasePattern, PatternResult


class ChainPattern(BasePattern):
    """
    Padrão Chain baseado em análise de âncoras e puxadas.

    history:
        Lista de números, com o MAIS RECENTE na posição 0.
    """

    def analyze(self, history: List[int]) -> PatternResult:
        """
        Analisa o histórico e retorna um PatternResult com:
        - candidatos: lista de números ordenados (ranking)
        - scores: dict {número: score_normalizado}
        - metadata: informações adicionais (âncoras, janelas, etc.)
        """
        # Validação básica de histórico
        min_size = self.get_config_value("min_size", 60)
        if not self.validate_history(history, min_size=min_size):
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={
                    "error": "Histórico insuficiente para análise Chain",
                    "history_size": len(history) if history else 0,
                    "min_size": min_size,
                },
                pattern_name=self.name,
            )

        # Configurações
        max_history = self.get_config_value("max_history", 200)
        anchor_window = self.get_config_value("anchor_window", 40)
        primary_window = self.get_config_value("primary_window", 5)
        extended_window = self.get_config_value("extended_window", 10)
        min_anchor_repeats = self.get_config_value("min_anchor_repeats", 2)
        max_anchors = self.get_config_value("max_anchors", 5)
        max_anchor_occurrences = self.get_config_value("max_anchor_occurrences", 4)
        top_candidates = self.get_config_value("top_candidates", 18)

        # Trabalhar com histórico cronológico (mais antigo primeiro)
        # history[0] é o mais recente -> invertendo
        hist = list(reversed(history[:max_history]))
        n = len(hist)

        # =========================
        # 1) Identificar âncoras
        # =========================
        chapter = hist[-anchor_window:] if n > anchor_window else hist
        count_chapter = Counter(chapter)

        # Âncoras: números que repetem pelo menos N vezes no capítulo
        anchors = [
            num for num, c in count_chapter.most_common()
            if c >= min_anchor_repeats
        ][:max_anchors]

        # Se não houver âncoras, faz fallback para frequência simples
        if not anchors:
            freq = Counter(chapter)
            scores_freq = {num: float(c) for num, c in freq.items()}
            scores_norm = self.normalize_scores(scores_freq)
            ordenados = sorted(
                scores_norm.items(), key=lambda x: x[1], reverse=True
            )[:top_candidates]
            candidatos = [num for num, _ in ordenados]

            return PatternResult(
                candidatos=candidatos,
                scores={num: score for num, score in ordenados},
                metadata={
                    "mode": "fallback_frequency",
                    "chapter_size": len(chapter),
                    "history_size": len(hist),
                },
                pattern_name=self.name,
            )

        # =========================
        # 2) Coletar puxadas por âncora
        # =========================
        primary_scores: Dict[int, float] = {}
        extended_scores: Dict[int, float] = {}
        anchor_stats: Dict[int, Dict[str, Any]] = {}

        for anchor in anchors:
            # Índices onde a âncora aparece no histórico cronológico
            idxs = [i for i, v in enumerate(hist) if v == anchor]
            if not idxs:
                continue

            # Considerar apenas as últimas ocorrências para o "humor" atual
            occurrences_considered = idxs[-max_anchor_occurrences:]

            followers_primary: Counter[int] = Counter()
            followers_extended: Counter[int] = Counter()

            for idx in occurrences_considered:
                # Olhar para frente até a janela estendida
                for offset in range(1, extended_window + 1):
                    j = idx + offset
                    if j >= n:
                        break
                    num = hist[j]
                    if offset <= primary_window:
                        followers_primary[num] += 1
                    followers_extended[num] += 1

            occ = len(occurrences_considered)
            if occ == 0:
                continue

            anchor_stats[anchor] = {
                "occurrences": occ,
                "followers_primary": dict(followers_primary),
                "followers_extended": dict(followers_extended),
            }

            # Peso da âncora: quanto mais aparece, mais forte
            weight_anchor = 1.0 + (occ - 1) * 0.3

            # Contribuição da âncora para os scores
            for num, c in followers_primary.items():
                primary_scores[num] = primary_scores.get(num, 0.0) + (c / occ) * weight_anchor

            for num, c in followers_extended.items():
                extended_scores[num] = (
                    extended_scores.get(num, 0.0)
                    + (c / occ) * weight_anchor * 0.7  # estendida vale um pouco menos
                )

        # Se por algum motivo não houver seguidores, aborta
        if not primary_scores and not extended_scores:
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={
                    "error": "Sem candidatos na análise Chain",
                    "anchors": anchors,
                    "history_size": len(hist),
                },
                pattern_name=self.name,
            )

        # =========================
        # 3) Combinar primary + extended
        # =========================
        combined_scores: Dict[int, float] = {}
        todos_numeros = set(primary_scores.keys()) | set(extended_scores.keys())

        for num in todos_numeros:
            combined_scores[num] = (
                primary_scores.get(num, 0.0)
                + extended_scores.get(num, 0.0)
            )

        # =========================
        # 4) Ajustes de "dívida" e recência
        # =========================
        # Dívida: números que ainda não apareceram no capítulo recente
        set_chapter = set(chapter)
        for num in combined_scores:
            if num not in set_chapter:
                combined_scores[num] *= 1.2  # leve bônus

        # Penalizar números ultra recentes (últimos 3)
        recent_block = hist[-3:]
        recent_set = set(recent_block)
        for num in combined_scores:
            if num in recent_set:
                combined_scores[num] *= 0.6

        # Remover o último número (mais recente de todos) do ranking
        ultimo_numero = hist[-1]
        if ultimo_numero in combined_scores:
            combined_scores.pop(ultimo_numero)

        # =========================
        # 5) Normalizar e montar ranking final
        # =========================
        scores_norm = self.normalize_scores(combined_scores)
        ordenados = sorted(
            scores_norm.items(), key=lambda x: x[1], reverse=True
        )[:top_candidates]

        candidatos = [num for num, _ in ordenados]
        scores_final = {num: score for num, score in ordenados}

        # Rankings separados por janela (útil para debug / dashboard)
        norm_primary = self.normalize_scores(primary_scores)
        norm_extended = self.normalize_scores(extended_scores)

        primary_ranking: List[Tuple[int, float]] = sorted(
            norm_primary.items(), key=lambda x: x[1], reverse=True
        )[:top_candidates]

        extended_ranking: List[Tuple[int, float]] = sorted(
            norm_extended.items(), key=lambda x: x[1], reverse=True
        )[:top_candidates]

        metadata = {
            "mode": "chain",
            "anchors": anchors,
            "anchor_stats": anchor_stats,
            "chapter_size": len(chapter),
            "history_size": len(hist),
            "primary_window": primary_window,
            "extended_window": extended_window,
            "primary_ranking": primary_ranking,
            "extended_ranking": extended_ranking,
        }

        return PatternResult(
            candidatos=candidatos,
            scores=scores_final,
            metadata=metadata,
            pattern_name=self.name,
        )