"""
patterns/pattern_estelar.py

🔱 ANÁLISE ESTELAR (versão simplificada)
Versão simplificada do padrão Estelar, focada na lógica de "ressonância" entre
a repetição de um mesmo número (alvo) e o contexto em que ele apareceu no passado.

Regras principais:
- Considera o último número sorteado como alvo (e agora pode testar até os 5 últimos).
- Procura uma ocorrência anterior desse mesmo alvo no histórico.
- Compara o contexto atual (número imediatamente anterior ao alvo) com o contexto
  dessa ocorrência anterior (dois números anteriores ao alvo nesse ponto).
- Se houver relação forte (igual, espelho, vizinho, terminal ou soma de dígitos),
  a aposta é construída a partir do número que veio DEPOIS da ocorrência anterior
  do alvo, expandindo para:
    - o próprio número
    - ±1
    - seus vizinhos de cilindro
    - seus espelhos
    - seus terminais
    - sua "figura" (derivada da soma de dígitos)
- Retorna um PatternResult, seguindo o padrão da BasePattern do projeto.
"""

from typing import Dict, List, Any, Optional
import logging

from patterns.base import BasePattern, PatternResult
from helpers.utils.filters import first_index_after, soma_digitos, get_numbers_by_terminal
from helpers.utils.get_figure import get_figure

logger = logging.getLogger(__name__)

# === Configurações da roleta ===

ROULETTE_WHEEL: List[int] = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36,
    11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9,
    22, 18, 29, 7, 28, 12, 35, 3, 26
]

# Espelhos fixos (mesma convenção usada no Estelar antigo)
MIRRORS: Dict[int, int] = {
    1: 10, 10: 1,
    2: 20, 20: 2,
    3: 30, 30: 3,
    6: 9,  9: 6,
    16: 19, 19: 16,
    26: 29, 29: 26,
    13: 31, 31: 13,
    12: 21, 21: 12,
    32: 23, 23: 32,
}

# Pesos padrão para os tipos de relação entre contextos
DEFAULT_RELATION_WEIGHTS: Dict[str, float] = {
    "igual": 5.0,
    "espelho": 4.0,
    "vizinho": 3.0,
    "terminal": 2.0,
    "soma_digitos": 1.0,
}


def get_neighbors(number: int, radius: int = 1) -> List[int]:
    """
    Retorna vizinhos de cilindro de um número, com raio especificado.
    Zero é tratado como central, mas não retornamos zero como vizinho.
    """
    if number not in ROULETTE_WHEEL:
        return []

    idx = ROULETTE_WHEEL.index(number)
    neighbors: List[int] = []

    for d in range(1, radius + 1):
        left_idx = (idx - d) % len(ROULETTE_WHEEL)
        right_idx = (idx + d) % len(ROULETTE_WHEEL)
        neighbors.append(ROULETTE_WHEEL[left_idx])
        neighbors.append(ROULETTE_WHEEL[right_idx])

    # Remove duplicados e o zero
    return sorted({n for n in neighbors if n != 0})


def get_mirrors(number: int) -> List[int]:
    """Retorna os espelhos de um número, se existirem."""
    if number in MIRRORS:
        return [MIRRORS[number]]
    return []


def get_terminal(number: int) -> int:
    """Retorna o terminal (último dígito) do número."""
    return abs(int(number)) % 10


def digit_sum(number: int) -> int:
    """Wrapper para soma de dígitos (pode usar o helper do projeto)."""
    try:
        # Usa a função já existente no projeto, se desejar manter centralizado
        return soma_digitos(number)
    except Exception:
        # Fallback simples caso algo dê errado
        return sum(int(d) for d in str(abs(int(number))))


def find_relations_between_lists(
    list1: List[int],
    list2: List[int],
    relation_weights: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    Compara todos os pares (a, b) entre duas listas e identifica relações:
    - igual
    - espelho
    - vizinho (raio 2)
    - terminal
    - soma_digitos

    Retorna uma lista de dicts:
    {
        "a": a,
        "b": b,
        "relations": ["igual", "terminal", ...],
        "score": soma_dos_pesos_dessas_relacoes
    }
    """
    if relation_weights is None:
        relation_weights = DEFAULT_RELATION_WEIGHTS

    relations: List[Dict[str, Any]] = []

    for a in list1:
        if a is None:
            continue

        mirrors_a = set(get_mirrors(a))
        neighbors_a = set(get_neighbors(a, radius=2))
        terminal_a = get_terminal(a)
        sum_a = digit_sum(a)

        for b in list2:
            if b is None:
                continue

            rel_types: List[str] = []

            # 1) Igual
            if a == b:
                rel_types.append("igual")

            # 2) Espelho
            if b in mirrors_a:
                rel_types.append("espelho")

            # 3) Vizinhos
            if b in neighbors_a:
                rel_types.append("vizinho")

            # 4) Mesmo terminal
            if terminal_a == get_terminal(b):
                rel_types.append("terminal")

            # 5) Mesma soma de dígitos
            if sum_a == digit_sum(b):
                rel_types.append("soma_digitos")

            if rel_types:
                score = sum(relation_weights.get(r, 0.0) for r in rel_types)
                relations.append(
                    {
                        "a": a,
                        "b": b,
                        "relations": rel_types,
                        "score": score,
                    }
                )

    return relations


class PatternEstelar(BasePattern):
    """
    Versão simplificada do padrão Estelar.

    Em vez de analisar todas as trincas e equivalências possíveis, focamos na
    lógica do estelar_novo:

    1. Pega o último número (alvo).
    2. Busca a próxima ocorrência desse alvo no histórico.
    3. Compara o contexto atual com o contexto dessa ocorrência.
    4. Se houver relação forte, aposta na região do número que veio depois
       dessa ocorrência anterior (after_value + vizinhos + espelhos + terminais + figura).

    ADAPTAÇÃO:
    - Se não houver relação para numbers[0], tenta numbers[1], depois numbers[2],
      até no máximo 5 números (índices 0..4), parando na primeira que gerar gatilho.
    """

    def __init__(self, config: Dict[str, Any] = None):
        if config is None:
            config = {}

        super().__init__(config)

        # Quantidade máxima de números a considerar do histórico
        self.memory_long: int = self.get_config_value("memory_long", 300)

        # Proteção no zero
        self.zero_protection: bool = self.get_config_value("zero_protection", True)

        # Pesos das relações entre contextos
        relation_weights = config.get("relation_weights") or DEFAULT_RELATION_WEIGHTS
        # Faz uma cópia para não modificar o dict global
        self.relation_weights: Dict[str, float] = dict(relation_weights)

        # Raio de vizinhos para montar a aposta (em torno do after_value)
        self.neighbor_radius: int = self.get_config_value("neighbor_radius", 1)

        # Quantos números recentes testar (ex: 5 → numbers[0]..numbers[4])
        self.max_offsets: int = self.get_config_value("max_offsets", 5)

    # ------------------------------------------------------------------
    # API principal usada pelo resto do sistema
    # ------------------------------------------------------------------
    def analyze(self, history: List[int]) -> PatternResult:
        """
        Recebe a lista de resultados (mais recente em history[0]) e retorna um
        PatternResult com:
            - candidatos: lista de números candidatos à jogada
            - scores: dict número -> score normalizado
            - metadata: dicionário com detalhes da análise
        """
        try:
            return self._analyze_internal(history)
        except Exception as e:
            logger.exception("Erro na análise Estelar simplificada: %s", e)
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={
                    "error": "Erro na análise Estelar simplificada",
                    "exception": str(e),
                },
                pattern_name=self.name,
            )

    # ------------------------------------------------------------------
    # Implementação com tentativa em até 5 números
    # ------------------------------------------------------------------
    def _analyze_internal(self, history: List[int]) -> PatternResult:
        # Validação mínima geral
        if not history or len(history) < 4:
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={"reason": "Histórico inválido ou insuficiente"},
                pattern_name=self.name,
            )

        # Garante que estamos usando apenas até memory_long resultados
        numbers: List[int] = history[: self.memory_long]

        # Vamos testar numbers[0], depois [1], [2]... até max_offsets (ou o tamanho do histórico)
        max_index = min(self.max_offsets, len(numbers) - 1)

        for idx_current in range(0, max_index + 1):
            result = self._analyze_for_index(numbers, idx_current)
            if result is not None:
                # Encontrou gatilho para algum dos 5 números testados -> retorna
                return result

        # Se chegou aqui, nenhum dos 5 números gerou relação
        return PatternResult(
            candidatos=[],
            scores={},
            metadata={
                "reason": "Nenhuma relação entre contextos nos últimos números",
                "max_offsets_checked": max_index + 1,
            },
            pattern_name=self.name,
        )

    # ------------------------------------------------------------------
    # Lógica original do estelar_novo adaptada para um índice específico
    # ------------------------------------------------------------------
    def _analyze_for_index(
        self,
        numbers: List[int],
        idx_current: int,
    ) -> Optional[PatternResult]:
        """
        Analisa um alvo específico em numbers[idx_current].

        Se não houver relação entre o contexto atual e o contexto da repetição
        anterior desse alvo, retorna None (não gatilhou para esse índice).
        Caso contrário, retorna um PatternResult com a jogada.
        """
        # Precisamos de pelo menos um número antes do alvo atual
        if idx_current + 1 >= len(numbers):
            return None

        alvo = numbers[idx_current]
        current_before = numbers[idx_current + 1]

        # Índice da próxima ocorrência do alvo no histórico (a partir do índice idx_current + 1)
        try:
            idx_prev = first_index_after(numbers, alvo, start=idx_current + 1)
        except Exception:
            # Fallback simples se o helper não estiver disponível / falhar
            idx_prev = None
            for i in range(idx_current + 1, len(numbers)):
                if numbers[i] == alvo:
                    idx_prev = i
                    break

        # Sem ocorrência anterior utilizável → sem gatilho nesse índice
        if idx_prev is None:
            return None

        # Precisamos de dois números antes e um depois dessa ocorrência anterior
        if idx_prev < 2 or idx_prev + 1 >= len(numbers):
            return None

        before_prev = numbers[idx_prev - 1]
        before_prev_2 = numbers[idx_prev - 2]
        after_prev = numbers[idx_prev + 1]

        # Monta listas para comparação de contexto
        # Lógica equivalente ao estelar_novo:
        #   l1 = [numbers[1]]                   (aqui: current_before)
        #   l2 = [before_check_1, numbers[check1 - 2]]
        l1 = [current_before]
        l2 = [before_prev, before_prev_2]

        relations = find_relations_between_lists(l1, l2, self.relation_weights)

        # Se não houver nenhuma relação entre os contextos, não gatilha para esse índice
        if not relations:
            return None

        # Calcula um score base usando a melhor relação encontrada
        base_relation_score = max((r["score"] for r in relations), default=0.0)
        if base_relation_score <= 0:
            base_relation_score = 1.0

        # Region core: número que veio depois da ocorrência anterior do alvo
        center = after_prev

        # Monta a região de aposta conforme estelar_novo,
        # mas corrigindo a questão de índice: usamos o valor center, não numbers[center]
        bet_set = set()

        # 1) Próprio número e ±1
        bet_set.add(center)
        bet_set.add(center - 1)
        bet_set.add(center + 1)

        # 2) Vizinhos de cilindro
        neighbors = get_neighbors(center, radius=self.neighbor_radius)
        bet_set.update(neighbors)

        # 3) Espelhos
        mirrors = get_mirrors(center)
        bet_set.update(mirrors)

        # 4) Terminais
        same_terminal = get_numbers_by_terminal(get_terminal(center))
        if isinstance(same_terminal, (list, tuple, set)):
            bet_set.update(same_terminal)

        # 5) Figura (com base na soma de dígitos)
        try:
            figure_numbers = get_figure(digit_sum(center))
        except Exception:
            figure_numbers = []

        if isinstance(figure_numbers, (list, tuple, set)):
            bet_set.update(figure_numbers)

        # Limpa aposta: apenas números válidos 0..36
        bet = sorted({n for n in bet_set if 0 <= n <= 36})

        # Se por algum motivo não sobrou nada, aborta esse índice
        if not bet:
            return None

        # Calcula scores por número com pesos relativos, mantendo a lógica qualitativa:
        scores: Dict[int, float] = {}

        for n in bet:
            if n == center:
                rel_factor = 1.0
            elif n in {center - 1, center + 1}:
                rel_factor = 0.9
            elif n in neighbors:
                rel_factor = 0.85
            elif n in mirrors:
                rel_factor = 0.8
            elif isinstance(same_terminal, (list, tuple, set)) and n in same_terminal:
                rel_factor = 0.7
            elif isinstance(figure_numbers, (list, tuple, set)) and n in figure_numbers:
                rel_factor = 0.6
            else:
                rel_factor = 0.5

            scores[n] = base_relation_score * rel_factor

        # Proteção no zero
        if self.zero_protection and 0 not in scores:
            scores[0] = base_relation_score * 0.3
            bet.append(0)

        # Normaliza scores usando a infra da BasePattern
        scores = self.normalize_scores(scores)

        metadata = {
            "reason": "Gatilho Estelar simplificado encontrado",
            "alvo": alvo,
            "current_index": idx_current,
            "alvo_previous_index": idx_prev,
            "before_prev": before_prev,
            "before_prev_2": before_prev_2,
            "after_prev": after_prev,
            "current_before": current_before,
            "center": center,
            "relations": relations,
            "memory_long_used": self.memory_long,
        }

        return PatternResult(
            candidatos=bet,
            scores=scores,
            metadata=metadata,
            pattern_name=self.name,
        )
