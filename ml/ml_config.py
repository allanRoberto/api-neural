# ml_config.py
"""
Configurações centrais do meta-modelo de sugestão.

Aqui ficam:
- parâmetros de janela de contexto
- parâmetros do padrão temporal
- lista de features esperadas pelo modelo
- configurações de K (quantidade de números sugeridos) e limiar de confiança
"""

from typing import List

# Números válidos da roleta (0 a 36)
NUMBERS: List[int] = list(range(37))

# Quantidade de giros usados como contexto para montar o estado
CONTEXT_WINDOW: int = 40

# Parâmetros do padrão temporal
TEMPORAL_DAYS: int = 30          # quantos dias para trás considerar
TEMPORAL_INTERVAL_MIN: int = 3   # largura da janela de horário (em minutos)

# Quantidade de números a sugerir
TOP_K_MIN: int = 12
TOP_K_MAX: int = 18
DEFAULT_TOP_K: int = 15          # valor padrão, pode ajustar depois

# Limiar inicial de confiança para decidir se vai sugerir ou pular a jogada
CONFIDENCE_THRESHOLD: float = 0.55  # ajustar depois via backtest

# Nomes das features por número.
# IMPORTANTE: essa lista define a "assinatura" do vetor de entrada do modelo.
FEATURE_NAMES: List[str] = [
    # Scores contínuos
    "s_master",
    "s_estelar",
    "s_chain",
    "s_comport",
    "s_temporal_freq",
    "s_temporal_rank_inv",   # rank invertido (maior = mais forte)

    # Flags de candidato por padrão
    "flag_candidate_master",
    "flag_candidate_estelar",
    "flag_candidate_chain",
    "flag_candidate_temporal_topk",

    # Relações estruturais
    "flag_vizinho",
    "flag_terminal",
    "flag_espelho",

    # Espaço para futuras features (placeholder)
    # "s_outro_padrao",
    # "flag_contexto_x",
]
