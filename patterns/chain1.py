"""
patterns/chain.py

Padrão CHAIN - Leitura narrativa da roleta (versão completa, sem ML).

Integra com a sua BasePattern:

- history: lista de ints (0..36) com MAIS RECENTE no índice 0
- método público: analyze(history) -> PatternResult
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter
import math

from patterns.base import BasePattern, PatternResult

# Ajuste estes imports para o que você já usa no projeto
try:
    from helpers.utils.filters import get_neighbords, get_mirror, get_terminal, is_consecutive
    
except ImportError:
    # Fallbacks mínimos para não quebrar; substitua pelos reais no seu projeto
    def get_neighbords(n: int) -> List[int]:
        return []

    def get_mirror(n: int):
        mirrors_map = {
            1: [10], 10: [1],
            2: [20], 20: [2],
            3: [30], 30: [3],
            6: [9], 9: [6],
            11: [22, 33],
            22: [11, 33],
            33: [11, 22],
            12: [21], 21: [12],
            13: [31], 31: [13],
            16: [19], 19: [16],
            23: [32], 32: [23],
            26: [29], 29: [26],
        }
        return mirrors_map.get(n, [])

    def get_terminal(n: int) -> int:
        return n % 10

    def is_consecutive(a: int, b: int) -> bool:
        return abs(a - b) == 1


# ──────────────────────────────────────────────────────────────────────────────
# ESTRUTURAS DE DADOS DO CHAIN
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ChainPull:
    """Representa uma puxada anchor -> m em até max_distance giros."""
    m: int
    count: int = 0
    distancias: List[int] = field(default_factory=list)

    @property
    def avg_dist(self) -> float:
        return sum(self.distancias) / len(self.distancias) if self.distancias else math.inf


@dataclass
class ChainBlock:
    """
    Bloco narrativo aprendido no histórico longo.

    Ex:
      sequencia = [27, 11, 36, 13]
      tipo      = "triangulo_vizinhanca"
      faltante  = 13
    """
    sequencia: List[int]
    tipo: str
    faltante: Optional[int] = None
    peso: float = 1.0


@dataclass
class ChainDebt:
    """
    Dívida aberta detectada no capítulo atual.

    Ex:
      motivo        = "crescente_incompleta"
      numeros_env   = [27, 28]
      faltante      = 29
      peso          = 1.0
    """
    motivo: str
    numeros_env: List[int]
    faltante: int
    peso: float = 0.6


@dataclass
class ChainKnowledge:
    """Conhecimento aprendido do histórico longo."""
    puxadas: Dict[int, List[ChainPull]] = field(default_factory=dict)
    blocos: List[ChainBlock] = field(default_factory=list)


@dataclass
class ChainResult:
    """Saída final interna do padrão CHAIN."""
    candidates: Dict[int, float]
    metadata: Dict[str, Any]


# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _unique_ints(nums: List[int]) -> List[int]:
    seen = set()
    out = []
    for n in nums:
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def _neighbors_k(n: int, k: int = 1) -> List[int]:
    """Expande vizinhos físicos em k camadas (usando get_neighbords)."""
    if k <= 0:
        return []
    fronteira = {n}
    visitados = {n}
    for _ in range(k):
        novos = set()
        for x in list(fronteira):
            for nb in get_neighbords(x):
                if nb not in visitados:
                    novos.add(nb)
                    visitados.add(nb)
        fronteira = novos
    visitados.discard(n)
    return _unique_ints([x for x in visitados if 0 <= x <= 36])


def _mirrors(n: int) -> List[int]:
    ms = get_mirror(n)
    if isinstance(ms, int):
        ms = [ms]
    return _unique_ints([int(x) for x in (ms or []) if 0 <= int(x) <= 36])


def _same_terminal(a: int, b: int) -> bool:
    return get_terminal(a) == get_terminal(b)


def _in_region(base: int, target: int, k: int = 1) -> bool:
    """
    Verifica se target está na mesma "região" do base:
      - o próprio número
      - vizinhos físicos até k
      - espelhos e vizinhos dos espelhos
    """
    if target == base:
        return True
    viz = set(_neighbors_k(base, k))
    if target in viz:
        return True
    for m in _mirrors(base):
        if target == m:
            return True
        if target in set(_neighbors_k(m, k)):
            return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# APRENDIZADO NO HISTÓRICO LONGO
# ──────────────────────────────────────────────────────────────────────────────

def _learn_puxadas(history: List[int], max_distance: int = 5) -> Dict[int, List[ChainPull]]:
    """
    Lê a história longa e descobre puxadas anchor -> m em até max_distance giros.

    history aqui deve estar do MAIS ANTIGO para o MAIS RECENTE.
    """
    pulls_map: Dict[int, Dict[int, ChainPull]] = defaultdict(dict)
    n = len(history)

    for i in range(n):
        anchor = history[i]
        for j in range(i + 1, min(i + 1 + max_distance, n)):
            m = history[j]
            dist = j - i
            inner = pulls_map[anchor]
            if m not in inner:
                inner[m] = ChainPull(m=m, count=0, distancias=[])
            inner[m].count += 1
            inner[m].distancias.append(dist)

    result: Dict[int, List[ChainPull]] = {}
    for anchor, inner in pulls_map.items():
        pulls = list(inner.values())
        pulls.sort(key=lambda p: (-p.count, p.avg_dist))
        result[anchor] = pulls

    return result


def _learn_blocks_from_history(history: List[int]) -> List[ChainBlock]:
    """
    Extrai blocos narrativos simplificados do histórico longo.

    history do MAIS ANTIGO para o MAIS RECENTE.
    """
    blocks: List[ChainBlock] = []
    n = len(history)

    # 1) crescents/decrescents simples de 3 números (a, b, c)
    for i in range(n - 2):
        a, b, c = history[i], history[i + 1], history[i + 2]
        # crescente numérica direta
        if b == a + 1 and c == b + 1 and 0 <= c <= 36:
            blocks.append(
                ChainBlock(
                    sequencia=[a, b, c],
                    tipo="crescente_numerica",
                    faltante=c,
                    peso=1.0,
                )
            )
        # decrescente numérica direta
        if b == a - 1 and c == b - 1 and 0 <= c <= 36:
            blocks.append(
                ChainBlock(
                    sequencia=[a, b, c],
                    tipo="decrescente_numerica",
                    faltante=c,
                    peso=1.0,
                )
            )

    # 2) triângulo de vizinhança tipo (x, y, z) devendo um 4º número "coerente"
    for i in range(n - 3):
        a, b, c, d = history[i], history[i + 1], history[i + 2], history[i + 3]

        cond_viz1 = _in_region(a, b, k=1) or _same_terminal(a, b)
        cond_viz2 = _in_region(a, c, k=1) or _same_terminal(a, c)
        if cond_viz1 and cond_viz2:
            blocks.append(
                ChainBlock(
                    sequencia=[a, b, c, d],
                    tipo="triangulo_vizinhanca",
                    faltante=d,
                    peso=1.0,
                )
            )

        if _in_region(a, c, k=1) and _in_region(b, d, k=1):
            blocks.append(
                ChainBlock(
                    sequencia=[a, b, c, d],
                    tipo="par_invertido",
                    faltante=d,
                    peso=0.8,
                )
            )

    return blocks


def learn_chain_knowledge(history: List[int], max_history: int = 200, max_distance: int = 5) -> ChainKnowledge:
    """
    Wrapper: recorta histórico longo (mais antigo -> mais recente),
    aprende puxadas e blocos.
    """
    if len(history) > max_history:
        long_history = history[-max_history:]
    else:
        long_history = list(history)

    puxadas = _learn_puxadas(long_history, max_distance=max_distance)
    blocos = _learn_blocks_from_history(long_history)

    return ChainKnowledge(puxadas=puxadas, blocos=blocos)


# ──────────────────────────────────────────────────────────────────────────────
# DETECÇÃO NO CAPÍTULO ATUAL (HISTÓRICO CURTO)
# ──────────────────────────────────────────────────────────────────────────────

def _detect_crescente_debts(recent: List[int]) -> List[ChainDebt]:
    """
    Detecta crescentes/decrescentes incompletas do tipo:
      27 -> 28 devendo 29
      28 -> 27 devendo 26 (simétrico)
    recent deve estar do MAIS ANTIGO para o MAIS RECENTE.
    """
    debts: List[ChainDebt] = []
    m = len(recent)
    if m < 2:
        return debts

    for i in range(m - 1):
        a, b = recent[i], recent[i + 1]
        # crescente simples numérica
        if b == a + 1 and 0 <= b + 1 <= 36:
            faltante = b + 1
            debts.append(
                ChainDebt(
                    motivo="crescente_incompleta",
                    numeros_env=[a, b],
                    faltante=faltante,
                    peso=1.0,
                )
            )
        # decrescente simples numérica
        if b == a - 1 and 0 <= b - 1 <= 36:
            faltante = b - 1
            debts.append(
                ChainDebt(
                    motivo="decrescente_incompleta",
                    numeros_env=[a, b],
                    faltante=faltante,
                    peso=1.0,
                )
            )

    return debts


def _detect_axis_debts(recent: List[int], knowledge: ChainKnowledge) -> List[ChainDebt]:
    """
    Inspiração Estudo C (eixo 10–20–11):

    Faz algo genérico:
      - para os últimos N âncoras (ex: 5 números finais),
      - olhamos as puxadas mais fortes,
      - se um número está muito conectado, tratamos como eixo,
        gerando faltantes por espelho e vizinho.
    """
    debts: List[ChainDebt] = []
    if len(recent) < 3:
        return debts

    anchors = list(dict.fromkeys(recent[-5:]))  # âncoras distintas nos últimos giros
    top_edges: Dict[Tuple[int, int], int] = Counter()

    for a in anchors:
        pulls = knowledge.puxadas.get(a, [])[:3]
        for p in pulls:
            top_edges[(a, p.m)] += p.count

    if not top_edges:
        return debts

    node_degree = Counter()
    for (a, b), cnt in top_edges.items():
        node_degree[a] += cnt
        node_degree[b] += cnt

    eixo_candidates = [n for n, deg in node_degree.items() if deg >= 2]
    if not eixo_candidates:
        return debts

    for n in eixo_candidates:
        for me in _mirrors(n):
            debts.append(
                ChainDebt(
                    motivo="eixo_espelho",
                    numeros_env=[n],
                    faltante=me,
                    peso=0.9,
                )
            )
        for nb in _neighbors_k(n, k=1):
            debts.append(
                ChainDebt(
                    motivo="eixo_vizinho",
                    numeros_env=[n],
                    faltante=nb,
                    peso=0.7,
                )
            )

    return debts


def _detect_triangle_debts(recent: List[int], knowledge: ChainKnowledge) -> List[ChainDebt]:
    """
    Inspiração Estudo A (triângulo 27–11–36 devendo 13 etc):

    Compara trechos recentes de 3 números com blocos "triangulo_vizinhanca".
    Se [a,b,c] é estruturalmente compatível com [A,B,C,D], propõe D como faltante.
    """
    debts: List[ChainDebt] = []
    m = len(recent)
    if m < 3:
        return debts

    trechos = []
    for i in range(m - 2):
        trechos.append(recent[i : i + 3])

    tri_blocks = [b for b in knowledge.blocos if b.tipo == "triangulo_vizinhanca" and len(b.sequencia) >= 4]

    for trecho in trechos:
        a, b, c = trecho
        for block in tri_blocks:
            A, B, C, D = block.sequencia[:4]

            match_a = _same_terminal(a, A) or _in_region(a, A, k=1)
            match_b = _same_terminal(b, B) or _in_region(b, B, k=1)
            match_c = _same_terminal(c, C) or _in_region(c, C, k=1)

            if match_a and match_b and match_c:
                faltante = block.faltante if block.faltante is not None else D
                debts.append(
                    ChainDebt(
                        motivo="triangulo_equivalente",
                        numeros_env=[a, b, c],
                        faltante=faltante,
                        peso=1.0,
                    )
                )

    return debts


def detect_chain_debts(recent: List[int], knowledge: ChainKnowledge) -> List[ChainDebt]:
    """
    Agrega vários tipos de dívidas:
      - crescentes/decrescentes incompletas
      - eixos (puxadas fortes)
      - triângulos equivalentes
    recent: mais antigo -> mais recente.
    """
    debts: List[ChainDebt] = []
    debts.extend(_detect_crescente_debts(recent))
    debts.extend(_detect_axis_debts(recent, knowledge))
    debts.extend(_detect_triangle_debts(recent, knowledge))

    by_faltante: Dict[int, float] = defaultdict(float)
    detalhes: Dict[int, List[str]] = defaultdict(list)

    for d in debts:
        by_faltante[d.faltante] += d.peso
        detalhes[d.faltante].append(d.motivo)

    merged: List[ChainDebt] = []
    for faltante, peso_total in by_faltante.items():
        motivos = ",".join(sorted(set(detalhes[faltante])))
        merged.append(
            ChainDebt(
                motivo=motivos,
                numeros_env=[],
                faltante=faltante,
                peso=peso_total,
            )
        )

    return merged


def build_chain_result(recent: List[int], knowledge: ChainKnowledge) -> ChainResult:
    """
    Gera ChainResult a partir do capítulo atual e do conhecimento.

    recent: mais antigo -> mais recente.
    """
    debts = detect_chain_debts(recent, knowledge)

    candidates: Dict[int, float] = defaultdict(float)
    for d in debts:
        candidates[d.faltante] += d.peso
        for me in _mirrors(d.faltante):
            candidates[me] += d.peso * 0.7

    if candidates:
        max_score = max(candidates.values())
        if max_score > 0:
            for n in list(candidates.keys()):
                candidates[n] = candidates[n] / max_score

    metadata: Dict[str, Any] = {
        "debts": [d.__dict__ for d in debts],
        "puxadas_top": {
            int(a): [
                {"m": p.m, "count": p.count, "avg_dist": p.avg_dist}
                for p in pulls[:3]
            ]
            for a, pulls in knowledge.puxadas.items()
        },
        "blocks_count": len(knowledge.blocos),
    }

    return ChainResult(candidates=dict(candidates), metadata=metadata)


# ──────────────────────────────────────────────────────────────────────────────
# PATTERNCHAIN INTEGRADO COM BasePattern
# ──────────────────────────────────────────────────────────────────────────────

class PatternChain(BasePattern):
    """
    Implementação do padrão CHAIN integrada à sua BasePattern.

    history recebido aqui: MAIS RECENTE no índice 0.
    Internamente, o CHAIN trabalha com mais antigo -> mais recente,
    então vamos inverter a lista no começo da analyze().
    """

    def __init__(
        self,
        config: Dict[str, Any] = None,
        max_history: int = 200,
        short_window: int = 15,
        max_distance: int = 5,
    ):
        super().__init__(config=config)
        self.max_history = max_history
        self.short_window = short_window
        self.max_distance = max_distance

    def analyze(self, history: List[int]) -> PatternResult:
        """
        Analisa o histórico e retorna PatternResult.

        Args:
            history: lista de ints (0..36) com MAIS RECENTE no índice 0.
        """
        # validação básica
        if not self.validate_history(history, min_size=10):
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={"reason": "historico_insuficiente"},
                pattern_name=self.name,
            )

        # Converte para ordem cronológica: MAIS ANTIGO -> MAIS RECENTE
        history_chrono = list(reversed(history))

        if len(history_chrono) > self.max_history:
            long_history = history_chrono[-self.max_history :]
        else:
            long_history = history_chrono

        if len(history_chrono) > self.short_window:
            recent = history_chrono[-self.short_window :]
        else:
            recent = history_chrono

        # aprende no histórico longo (regras fixas)
        knowledge = learn_chain_knowledge(
            long_history,
            max_history=self.max_history,
            max_distance=self.max_distance,
        )

        # capítulo atual -> dívidas -> candidatos
        chain_result = build_chain_result(recent, knowledge)

        # normaliza scores usando helper da BasePattern
        normalized_scores = self.normalize_scores(chain_result.candidates)

        # candidatos = números com score > 0 (ordenados opcionalmente)
        candidatos = sorted(normalized_scores.keys(), key=lambda n: normalized_scores[n], reverse=True)

        metadata = dict(chain_result.metadata)
        metadata.update(
            {
                "history_size": len(history),
                "recent_size": len(recent),
                "max_history": self.max_history,
                "short_window": self.short_window,
            }
        )

        return PatternResult(
            candidatos=candidatos,
            scores=normalized_scores,
            metadata=metadata,
            pattern_name=self.name,
        )
