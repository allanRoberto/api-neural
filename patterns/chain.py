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

ADAPTAÇÃO:
- scores agora são um "campo de força" completo:
    - seguidores diretos das âncoras
    - vizinhos dos seguidores
    - espelhos dos seguidores
- PatternResult.scores contém o mapa COMPLETO normalizado (0–1),
  e candidatos são apenas o top N desse mapa.
"""

from typing import List, Dict, Any, Tuple
from collections import Counter

from .base import BasePattern, PatternResult
from helpers.utils.filters import get_neighbords, get_mirror


class ChainPattern(BasePattern):
    """
    Padrão Chain baseado em análise de âncoras e puxadas.

    history:
        Lista de números, com o MAIS RECENTE na posição 0.
    """

    # pesos para propagação da "força" do Chain
    W_SELF = 1.0        # peso do próprio número
    W_NEIGHBOR = 0.6    # peso propagado para vizinhos
    W_MIRROR = 0.4      # peso propagado para espelhos

    def analyze(self, history: List[int]) -> PatternResult:
        """
        Analisa o histórico e retorna um PatternResult com:
        - candidatos: lista de números ordenados (ranking)
        - scores: dict {número: score_normalizado} (MAPA COMPLETO)
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
        top_candidates = self.get_config_value("top_candidates", 12)

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

        # =========================
        # Fallback: sem âncoras => frequência simples
        # =========================
        if not anchors:
            freq = Counter(chapter)
            base_scores = {num: float(c) for num, c in freq.items()}

            # Aplica dívida/recência + vizinhos/espelhos
            chain_scores = self._build_chain_scores(
                hist=hist,
                chapter=chapter,
                base_scores=base_scores,
            )

            if not chain_scores:
                return PatternResult(
                    candidatos=[],
                    scores={},
                    metadata={
                        "mode": "fallback_frequency_empty",
                        "chapter_size": len(chapter),
                        "history_size": len(hist),
                    },
                    pattern_name=self.name,
                )

            scores_norm_full = self.normalize_scores(chain_scores)
            ordenados = sorted(
                scores_norm_full.items(),
                key=lambda x: x[1],
                reverse=True
            )

            candidatos = [num for num, _ in ordenados[:top_candidates]]

            return PatternResult(
                candidatos=candidatos,
                scores=scores_norm_full,
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

            # Contribuição da âncora para os scores "brutos" de Chain
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
        # 4) Aplicar dívida, recência e campo de força (vizinhos + espelhos)
        # =========================
        chain_scores = self._build_chain_scores(
            hist=hist,
            chapter=chapter,
            base_scores=combined_scores,
        )

        # =========================
        # 5) Normalizar e montar ranking final
        # =========================
        scores_norm_full = self.normalize_scores(chain_scores)

        ordenados = sorted(
            scores_norm_full.items(),
            key=lambda x: x[1],
            reverse=True
        )

        candidatos = [num for num, _ in ordenados[:top_candidates]]

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
            candidatos=candidatos[:12],
            scores=scores_norm_full,
            metadata=metadata,
            pattern_name=self.name,
        )

    # ======================================================================
    # Helpers internos do padrão Chain
    # ======================================================================

    def _build_chain_scores(
        self,
        hist: List[int],
        chapter: List[int],
        base_scores: Dict[int, float],
    ) -> Dict[int, float]:
        """
        Aplica:
        - bônus de dívida (números que ainda não apareceram no capítulo);
        - penalização por recência (últimos 3 giros);
        - remoção do último número;
        - propagação de força para vizinhos e espelhos.

        Retorna um dict {numero: score_final} (AINDA NÃO NORMALIZADO).
        """
        if not base_scores:
            return {}

        # Copiar para não alterar dict externo
        scores = dict(base_scores)

        # 1) Dívida: números que ainda não saíram no capítulo recente
        set_chapter = set(chapter)
        for num in list(scores.keys()):
            if num not in set_chapter:
                scores[num] *= 1.2  # leve bônus

        # 2) Penalizar números ultra recentes (últimos 3)
        recent_block = hist[-3:] if len(hist) >= 3 else hist
        recent_set = set(recent_block)
        for num in list(scores.keys()):
            if num in recent_set:
                scores[num] *= 0.6

        # 3) Remover o último número (mais recente de todos) do ranking
        if hist:
            ultimo_numero = hist[-1]
            if ultimo_numero in scores:
                scores.pop(ultimo_numero)

        # 4) Campo de força: propagar para vizinhos e espelhos
        spread_scores: Dict[int, float] = {}

        for num, base_val in scores.items():
            # próprio número
            spread_scores[num] = spread_scores.get(num, 0.0) + base_val * self.W_SELF

            # vizinhos
            try:
                neighbors = get_neighbords(num)
            except Exception:
                neighbors = []

            for viz in neighbors:
                if 0 <= viz <= 36:
                    spread_scores[viz] = spread_scores.get(viz, 0.0) + base_val * self.W_NEIGHBOR

            # espelhos
            try:
                mirrors = get_mirror(num)
            except Exception:
                mirrors = []

            if isinstance(mirrors, int):
                mirrors = [mirrors]

            for esp in mirrors:
                if 0 <= esp <= 36:
                    spread_scores[esp] = spread_scores.get(esp, 0.0) + base_val * self.W_MIRROR

        return spread_scores