# feature_extractor.py
"""
Responsável por transformar o estado atual da roleta
(historico + horário) em um vetor de features por número.

Saída principal:
    extract_features_for_state(history, now_dt)
        -> {numero: {feature_name: valor}}

Esse módulo NÃO treina nada, só organiza os sinais dos padrões
em forma numérica para o meta-modelo.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import logging

from ml.ml_config import (
    NUMBERS,
    FEATURE_NAMES,
    CONTEXT_WINDOW,
    TEMPORAL_DAYS,
    TEMPORAL_INTERVAL_MIN,
)

# ==== IMPORTS DOS PADRÕES ====
# Ajuste os caminhos conforme a estrutura real do seu projeto.
from patterns.estelar import PatternEstelar
from patterns.master import PatternMaster
from patterns.chain import ChainAnalyzer
from patterns.comportamentos_imediatos import ComportamentosImediatos

logger = logging.getLogger(__name__)

FeatureDict = Dict[str, float]
FeaturesByNumber = Dict[int, FeatureDict]

# Instâncias únicas (singletons) dos padrões
_ESTELAR_INSTANCE: Optional[PatternEstelar] = None
_MASTER_INSTANCE: Optional[PatternMaster] = None
_CHAIN_INSTANCE: Optional[ChainAnalyzer] = None
_COMPORT_INSTANCE: Optional[ComportamentosImediatos] = None


def _get_estelar_instance() -> PatternEstelar:
    """
    Retorna uma instância singleton do PatternEstelar.
    """
    global _ESTELAR_INSTANCE
    if _ESTELAR_INSTANCE is None:
        config_estelar = {
        'max_gap_between_elements': 2,
        'memory_short': 10,
        'memory_long': 200,
        'enable_inversions': True,
        'enable_compensation': True,
        'verbose': False,
        'equivalence_weights': {
            'EXACT': 1.0,
            'NEIGHBOR': 0.8,
            'TERMINAL': 0.6,
            'MIRROR': 0.5,
            'PROPERTY': 0.4,
            'BEHAVIORAL': 0.3
        }
        }
        _ESTELAR_INSTANCE = PatternEstelar(config=config_estelar)
    return _ESTELAR_INSTANCE


def _get_master_instance() -> PatternMaster:
    """
    Retorna uma instância singleton do PatternMaster.
    """
    global _MASTER_INSTANCE
    if _MASTER_INSTANCE is None:

        config_master = {
            'enable_combined': True,     # Habilita D1Par, D2Ímpar, etc
            'enable_blocks': True,       # Habilita bloqueios (ciclo exausto)
            'cycle_detection': True,     # Detecta ciclos completos
            'verbose': False             # Modo silencioso
        }
         
        _MASTER_INSTANCE = PatternMaster(config=config_master)
    return _MASTER_INSTANCE


def _get_chain_instance() -> ChainAnalyzer:
    """
    Retorna uma instância singleton do ChainAnalyzer.
    """
    global _CHAIN_INSTANCE
    if _CHAIN_INSTANCE is None:
        _CHAIN_INSTANCE = ChainAnalyzer()
    return _CHAIN_INSTANCE


def _get_comport_instance() -> ComportamentosImediatos:
    """
    Retorna uma instância singleton do ComportamentosImediatos.
    """
    global _COMPORT_INSTANCE
    if _COMPORT_INSTANCE is None:
        _COMPORT_INSTANCE = ComportamentosImediatos()
    return _COMPORT_INSTANCE


def _init_empty_features() -> FeaturesByNumber:
    """
    Cria o dicionário base com todas as features zeradas para cada número.
    """
    return {
        n: {name: 0.0 for name in FEATURE_NAMES}
        for n in NUMBERS
    }


# ============
# HELPER: MASTER (PLUGADO)
# ============

def _compute_master_features(history: List[int]) -> Dict[int, Dict[str, float]]:
    """
    Retorna, para cada número, um dict com:
        - "score": força do padrão MASTER para esse número
        - "candidate": 1.0 se o número é candidato no MASTER, 0.0 caso contrário

    history:
        Lista de números (mais recente no índice 0) – padrão dos patterns.
    """
    results: Dict[int, Dict[str, float]] = {
        n: {"score": 0.0, "candidate": 0.0}
        for n in NUMBERS
    }

    master = _get_master_instance()

    try:
        pattern_result = master.analyze(history)
    except Exception as e:
        logger.exception(f"Erro ao analisar MASTER: {e}")
        return results

    scores = getattr(pattern_result, "scores", {}) or {}
    candidatos = set(getattr(pattern_result, "candidatos", []) or [])

    for n in NUMBERS:
        results[n]["score"] = float(scores.get(n, 0.0))
        results[n]["candidate"] = 1.0 if n in candidatos else 0.0

    return results


# ============
# HELPER: ESTELAR (PLUGADO)
# ============

def _compute_estelar_features(history: List[int]) -> Dict[int, Dict[str, float]]:
    """
    Retorna, para cada número, um dict com:
        - "score": força do padrão ESTELAR para esse número
        - "candidate": 1.0 se o número é C (ou equivalente) de alguma trinca ativa

    history:
        Lista de números (mais recente no índice 0).
    """
    results: Dict[int, Dict[str, float]] = {
        n: {"score": 0.0, "candidate": 0.0}
        for n in NUMBERS
    }

    estelar = _get_estelar_instance()

    try:
        pattern_result = estelar.analyze(history)
    except Exception as e:
        logger.exception(f"Erro ao analisar ESTELAR: {e}")
        return results

    scores = getattr(pattern_result, "scores", {}) or {}
    candidatos = set(getattr(pattern_result, "candidatos", []) or [])

    for n in NUMBERS:
        results[n]["score"] = float(scores.get(n, 0.0))
        results[n]["candidate"] = 1.0 if n in candidatos else 0.0

    return results


# ============
# HELPER: CHAIN (PLUGADO)
# ============

def _compute_chain_features(history: List[int]) -> Dict[int, Dict[str, float]]:
    """
    Retorna, para cada número, um dict com:
        - "score": força do padrão CHAIN (elos/dívidas/faltantes)
        - "candidate": 1.0 se o número é faltante/âncora de fechamento etc.

    history:
        Lista de números (mais recente no índice 0).
    """
    results: Dict[int, Dict[str, float]] = {
        n: {"score": 0.0, "candidate": 0.0}
        for n in NUMBERS
    }

    chain = _get_chain_instance()

    try:
        pattern_result = chain.analyze(history)
    except Exception as e:
        logger.exception(f"Erro ao analisar CHAIN: {e}")
        return results

    scores = getattr(pattern_result, "scores", {}) or {}
    candidatos = set(getattr(pattern_result, "candidatos", []) or []

                     )

    for n in NUMBERS:
        results[n]["score"] = float(scores.get(n, 0.0))
        results[n]["candidate"] = 1.0 if n in candidatos else 0.0

    return results


# ============
# HELPER: COMPORTAMENTOS IMEDIATOS (PLUGADO)
# ============

def _compute_comport_features(history: List[int]) -> Dict[int, Dict[str, float]]:
    """
    Retorna, para cada número, um dict com:
        - "score": força dos comportamentos imediatos para esse número
        - "candidate": 1.0 se o número é alvo de confirmação imediata
    """
    results: Dict[int, Dict[str, float]] = {
        n: {"score": 0.0, "candidate": 0.0}
        for n in NUMBERS
    }

    comp = _get_comport_instance()

    try:
        pattern_result = comp.analyze(history)
    except Exception as e:
        logger.exception(f"Erro ao analisar COMPORTAMENTOS IMEDIATOS: {e}")
        return results

    scores = getattr(pattern_result, "scores", {}) or {}
    candidatos = set(getattr(pattern_result, "candidatos", []) or [])

    for n in NUMBERS:
        results[n]["score"] = float(scores.get(n, 0.0))
        # se quiser usar candidate depois, já está disponível aqui
        results[n]["candidate"] = 1.0 if n in candidatos else 0.0

    return results


# ============
# HELPER: TEMPORAL
# ============

def _compute_temporal_features(
    now_dt: datetime,
    roulette_id: str | None = None,
) -> Dict[int, Dict[str, float]]:
    """
    Retorna, para cada número, um dict com:
        - "freq": frequência relativa nos últimos TEMPORAL_DAYS nesse horário
        - "rank_inv": rank invertido (maior valor = mais frequente)

    Aqui NÃO usamos o history local, e sim o histórico global de N dias.
    A ideia é consultar o banco para buscar os resultados desse horário.
    """
    results: Dict[int, Dict[str, float]] = {
        n: {"freq": 0.0, "rank_inv": 0.0}
        for n in NUMBERS
    }

    # TODO:
    # 1) Buscar no banco todos os resultados da roleta nessa faixa de horário
    #    nos últimos TEMPORAL_DAYS.
    # 2) Contar ocorrências por número.
    # 3) Normalizar para [0, 1] (freq) e calcular o rank invertido.

    return results


# ============
# HELPER: RELAÇÕES (VIZINHO / TERMINAL / ESPELHO)
# ============

def _compute_relational_flags(history: List[int]) -> Dict[int, Dict[str, float]]:
    """
    Retorna, para cada número, flags de:
        - vizinho
        - terminal
        - espelho

    A ideia aqui é olhar para o contexto recente (último número, últimos N)
    e marcar quais números estão conectados a esses núcleos.

    TODO: plugar aqui suas funções reais de:
        - get_neighbors
        - get_terminals
        - get_mirror
    """
    results: Dict[int, Dict[str, float]] = {
        n: {
            "flag_vizinho": 0.0,
            "flag_terminal": 0.0,
            "flag_espelho": 0.0,
        }
        for n in NUMBERS
    }

    # Exemplo quando plugar:
    # last_num = history[0]  # mais recente
    # vizinhos = get_neighbors(last_num)
    # terminais = get_terminals(last_num)
    # espelhos = get_mirror(last_num)
    #
    # for n in vizinhos:
    #     results[n]["flag_vizinho"] = 1.0
    # for n in terminais:
    #     results[n]["flag_terminal"] = 1.0
    # for n in espelhos:
    #     results[n]["flag_espelho"] = 1.0

    return results


# ============
# FUNÇÃO PRINCIPAL
# ============

def extract_features_for_state(
    history: List[int],
    now_dt: datetime,
    roulette_id: str | None = None,
) -> FeaturesByNumber:
    """
    Constrói o vetor de features por número para o estado atual.

    history:
        Lista de resultados, com o MAIS RECENTE no índice 0.
        (Esse é o padrão da BasePattern e dos patterns que você já tem.)

    now_dt:
        Datetime atual, usado para o padrão temporal.

    roulette_id:
        Opcional, caso você diferencie padrões/temporais por mesa.
    """
    if len(history) < CONTEXT_WINDOW:
        raise ValueError(
            f"history com {len(history)} giros; precisa de pelo menos {CONTEXT_WINDOW}"
        )

    features: FeaturesByNumber = _init_empty_features()

    # --- 1) MASTER ---
    master = _compute_master_features(history)
    for n in NUMBERS:
        features[n]["s_master"] = master[n]["score"]
        features[n]["flag_candidate_master"] = master[n]["candidate"]

    # --- 2) ESTELAR ---
    estelar = _compute_estelar_features(history)
    for n in NUMBERS:
        features[n]["s_estelar"] = estelar[n]["score"]
        features[n]["flag_candidate_estelar"] = estelar[n]["candidate"]

    # --- 3) CHAIN ---
    chain = _compute_chain_features(history)
    for n in NUMBERS:
        features[n]["s_chain"] = chain[n]["score"]
        features[n]["flag_candidate_chain"] = chain[n]["candidate"]

    # --- 4) COMPORTAMENTOS IMEDIATOS ---
    comport = _compute_comport_features(history)
    for n in NUMBERS:
        features[n]["s_comport"] = comport[n]["score"]
        # se quiser, você pode adicionar uma FEATURE_NAME
        # "flag_candidate_comport" no ml_config e setar aqui:
        # features[n]["flag_candidate_comport"] = comport[n]["candidate"]

    # --- 5) TEMPORAL ---
    temporal = _compute_temporal_features(now_dt, roulette_id=roulette_id)

    # Descobre qual é o top-K temporal para setar flag (ex.: top 15)
    ordered_by_freq = sorted(
        NUMBERS,
        key=lambda x: temporal[x]["freq"],
        reverse=True,
    )
    top_temporal_k = set(ordered_by_freq[:15])

    for n in NUMBERS:
        features[n]["s_temporal_freq"] = temporal[n]["freq"]
        features[n]["s_temporal_rank_inv"] = temporal[n]["rank_inv"]
        features[n]["flag_candidate_temporal_topk"] = 1.0 if n in top_temporal_k else 0.0

    # --- 6) RELAÇÕES (VIZINHO / TERMINAL / ESPELHO) ---
    rel = _compute_relational_flags(history)
    for n in NUMBERS:
        features[n]["flag_vizinho"] = rel[n]["flag_vizinho"]
        features[n]["flag_terminal"] = rel[n]["flag_terminal"]
        features[n]["flag_espelho"] = rel[n]["flag_espelho"]

    return features
