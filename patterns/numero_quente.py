"""
patterns/numero_quente.py

Padrão de NÚMEROS QUENTES integrado ao modelo BasePattern / PatternResult.

Ideia geral:
- Usa apenas o histórico recebido (lista de números, mais recente na posição 0).
- Considera uma janela recente de giros (ex.: últimos 200).
- Calcula:
    * frequência de cada número na janela
    * "lift" em relação à frequência esperada (janela / 37)
    * bônus de recência (streak nos últimos X giros)

- Gera um score base para cada número combinando:
    * frequência normalizada
    * lift normalizado
    * bônus de recência

- Propaga esse score base para:
    * o próprio número (peso W_SELF)
    * vizinhos do número (W_NEIGHBOR)
    * espelhos do número (W_MIRROR)

- Devolve:
    * PatternResult.candidatos: top N números quentes
    * PatternResult.scores: mapa COMPLETO {numero: score_normalizado} (0–1)
    * PatternResult.metadata: informações de debug (freq, lift, janela etc.)
"""

from typing import List, Dict, Any
from collections import Counter

from .base import BasePattern, PatternResult
from helpers.utils.filters import get_neighbords, get_mirror


class HotNumbersPattern(BasePattern):
    """
    Padrão de NÚMEROS QUENTES.

    history:
        Lista de números, com o MAIS RECENTE na posição 0.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Configuração padrão (pode ser sobrescrita via config ou kwargs):

        - window_size:    quantidade de giros recentes para analisar (ex.: 200)
        - min_size:       tamanho mínimo de histórico para considerar o padrão
        - short_window:   janela curta para streak (ex.: últimos 20 giros)
        - top_candidates: quantidade de candidatos principais (ex.: 18)
        - lift_cap:       valor de lift considerado "muito quente" (ex.: 1.8)
        - freq_weight:    peso da frequência normalizada
        - lift_weight:    peso do lift normalizado
        - streak_weight:  peso da recência/streak
        - w_self:         peso do próprio número na propagação
        - w_neighbor:     peso dos vizinhos
        - w_mirror:       peso dos espelhos
        """
        super().__init__(config=config)

        # parâmetros com default; se vierem em config, BasePattern.get_config_value cuida
        self.window_size    = self.get_config_value("window_size", 200)
        self.min_size       = self.get_config_value("min_size", 60)
        self.short_window   = self.get_config_value("short_window", 50)
        self.top_candidates = self.get_config_value("top_candidates", 18)
        self.lift_cap       = self.get_config_value("lift_cap", 1.8)

        self.freq_weight    = self.get_config_value("freq_weight", 0.8)
        self.lift_weight    = self.get_config_value("lift_weight", 0.3)
        self.streak_weight  = self.get_config_value("streak_weight", 0.2)

        self.w_self         = self.get_config_value("w_self", 1.0)
        self.w_neighbor     = self.get_config_value("w_neighbor", 0.9)
        self.w_mirror       = self.get_config_value("w_mirror", 0.8)

    def analyze(self, history: List[int]) -> PatternResult:
        """
        Analisa o histórico e retorna um PatternResult com:
        - candidatos: top N números quentes (ordenados por score)
        - scores: mapa COMPLETO {número: score_normalizado}
        - metadata: detalhes da análise
        """
        # Validação básica de histórico
        if not self.validate_history(history, min_size=self.min_size):
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={
                    "error": "Histórico insuficiente para análise de números quentes",
                    "history_size": len(history) if history else 0,
                    "min_size": self.min_size,
                },
                pattern_name=self.name,
            )

        # Janela de análise: últimos N giros (histórico chega com mais recente em index 0)
        # => pegamos os window_size mais recentes
        window = history[: self.window_size]
        window_size_real = len(window)

        if window_size_real == 0:
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={
                    "error": "Janela de análise vazia para números quentes",
                    "window_size": self.window_size,
                },
                pattern_name=self.name,
            )

        # Frequência dos números na janela
        freq = Counter(window)
        max_freq = max(freq.values()) if freq else 0

        # Frequência esperada por número (janela / 37)
        expected = window_size_real / 37.0

        # Janela curta para streak/recência (subconjunto da janela)
        short_window_size = min(self.short_window, window_size_real)
        short_window = window[:short_window_size]
        short_freq = Counter(short_window)

        base_scores: Dict[int, float] = {}
        freq_raw: Dict[int, int] = {}
        lift_raw: Dict[int, float] = {}
        streak_raw: Dict[int, int] = {}

        for n in range(37):
            f = freq.get(n, 0)
            freq_raw[n] = f

            # Normalização da frequência (0–1)
            if max_freq > 0:
                freq_norm = f / max_freq
            else:
                freq_norm = 0.0

            # Lift em relação ao esperado
            if expected > 0:
                lift = f / expected
            else:
                lift = 0.0
            lift_raw[n] = lift

            # Normalizar lift para 0–1:
            #   <=1.0  => 0
            #   >=lift_cap => 1
            if lift <= 1.0:
                lift_norm = 0.0
            elif lift >= self.lift_cap:
                lift_norm = 1.0
            else:
                lift_norm = (lift - 1.0) / (self.lift_cap - 1.0)

            # Bônus de recência/streak na janela curta
            sf = short_freq.get(n, 0)
            streak_raw[n] = sf
            if sf >= 3:
                streak_bonus = 1.0
            elif sf == 2:
                streak_bonus = 0.7
            elif sf == 1:
                streak_bonus = 0.4
            else:
                streak_bonus = 0.0

            # Score base combinando os três componentes
            base_score = (
                self.freq_weight * freq_norm
                + self.lift_weight * lift_norm
                + self.streak_weight * streak_bonus
            )

            if base_score > 0:
                base_scores[n] = base_score

        if not base_scores:
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={
                    "error": "Nenhum número considerado quente na janela atual",
                    "window_size": window_size_real,
                },
                pattern_name=self.name,
            )

        # Propagação para vizinhos e espelhos -> campo de força
        spread_scores: Dict[int, float] = {}

        for num, val in base_scores.items():
            # próprio número
            spread_scores[num] = spread_scores.get(num, 0.0) + val * self.w_self

            # vizinhos na roda
            try:
                vizinhos = get_neighbords(num)
            except Exception:
                vizinhos = []

            for v in vizinhos:
                if 0 <= v <= 36:
                    spread_scores[v] = spread_scores.get(v, 0.0) + val * self.w_neighbor


             # vizinhos na roda
            try:
                vizinhos2 = get_neighbords(num, 2)
            except Exception:
                vizinhos2 = []

            for v in vizinhos2:
                if 0 <= v <= 36:
                    spread_scores[v] = spread_scores.get(v, 0.0) + val * self.w_neighbor

            # espelhos
            try:
                mirrors = get_mirror(num)
            except Exception:
                mirrors = []

            if isinstance(mirrors, int):
                mirrors = [mirrors]

            for m in mirrors:
                if 0 <= m <= 36:
                    spread_scores[m] = spread_scores.get(m, 0.0) + val * self.w_mirror

        # Normalizar o campo de força final
        scores_norm = self.normalize_scores(spread_scores)

        # Candidatos: top N por score
        ordenados = sorted(scores_norm.items(), key=lambda x: x[1], reverse=True)
        candidatos = [num for num, _ in ordenados[: self.top_candidates]]

        # Montar metadata rica para debug e futuras métricas de confiança
        top_hot_debug = []
        for num, _score in ordenados[: self.top_candidates]:
            top_hot_debug.append({
                "number": num,
                "freq": freq_raw.get(num, 0),
                "lift": round(lift_raw.get(num, 0.0), 3),
                "streak": streak_raw.get(num, 0),
                "score": round(scores_norm.get(num, 0.0), 4),
            })

        metadata = {
            "mode": "hot_numbers",
            "window_size": self.window_size,
            "window_size_real": window_size_real,
            "short_window": short_window_size,
            "expected_per_number": expected,
            "lift_cap": self.lift_cap,
            "freq_weight": self.freq_weight,
            "lift_weight": self.lift_weight,
            "streak_weight": self.streak_weight,
            "w_self": self.w_self,
            "w_neighbor": self.w_neighbor,
            "w_mirror": self.w_mirror,
            "top_hot": top_hot_debug,
        }

        return PatternResult(
            candidatos=candidatos[:12],
            scores=scores_norm,
            metadata=metadata,
            pattern_name=self.name,
        )


def create_hot_numbers_pattern(**kwargs) -> HotNumbersPattern:
    """
    Helper para criar instância já configurada do padrão de números quentes.

    Exemplo:
        hot_pattern = create_hot_numbers_pattern(window_size=200, top_candidates=18)
    """
    return HotNumbersPattern(config=kwargs)