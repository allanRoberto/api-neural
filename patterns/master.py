"""
patterns/pattern_master.py

⚙️ ANÁLISE MASTER - Pattern Recognition Module
Sistema de reconhecimento baseado em propriedades objetivas e mensuráveis.
Valida comportamentos através de estruturas fixas: dúzia, coluna, cor, paridade, faixa e grupos.
"""

from typing import Dict, List, Tuple, Set, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict, Counter, deque
from datetime import datetime
import logging
from enum import Enum

# Importa a classe base
from patterns.base import BasePattern, PatternResult

logger = logging.getLogger(__name__)


class PropertyType(Enum):
    """Tipos de propriedades analisadas"""
    DOZEN = "dozen"           # Dúzia (D1, D2, D3)
    COLUMN = "column"         # Coluna (C1, C2, C3)
    COLOR = "color"           # Cor (vermelho, preto)
    PARITY = "parity"         # Paridade (par, ímpar)
    RANGE = "range"           # Faixa (baixo 1-18, alto 19-36)
    GROUP = "group"           # Grupo estrutural (Voisins, Tiers, Orphelins)
    COMBINED = "combined"     # Combinações (D1Par, D2Ímpar, etc)


class RouletteProperties:
    """Propriedades objetivas da roleta europeia"""
    
    # Ordem dos números no cilindro
    WHEEL_ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
    
    # Cores
    RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
    BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
    
    # Grupos estruturais do cilindro
    VOISINS = {0, 2, 3, 4, 7, 12, 15, 18, 19, 21, 22, 25, 26, 28, 29, 32, 35}
    TIERS = {5, 8, 10, 11, 13, 16, 23, 24, 27, 30, 33, 36}
    ORPHELINS = {1, 6, 9, 14, 17, 20, 31, 34}
    
    @classmethod
    def get_all_properties(cls, num: int) -> Dict[str, Any]:
        """Retorna todas as propriedades de um número"""
        if num == 0:
            return {
                'number': 0,
                'dozen': 0,
                'column': 0,
                'color': 'green',
                'parity': 'zero',
                'range': 'zero',
                'group': 'voisins',
                'combined': 'zero'
            }
        
        props = {
            'number': num,
            'dozen': cls.get_dozen(num),
            'column': cls.get_column(num),
            'color': cls.get_color(num),
            'parity': cls.get_parity(num),
            'range': cls.get_range(num),
            'group': cls.get_group(num)
        }
        
        # Propriedade combinada (Dúzia + Paridade)
        props['combined'] = f"D{props['dozen']}{props['parity'][0].upper()}"
        
        return props
    
    @classmethod
    def get_dozen(cls, num: int) -> int:
        """Retorna a dúzia (1, 2 ou 3)"""
        if num == 0:
            return 0
        return (num - 1) // 12 + 1
    
    @classmethod
    def get_column(cls, num: int) -> int:
        """Retorna a coluna (1, 2 ou 3)"""
        if num == 0:
            return 0
        return ((num - 1) % 3) + 1
    
    @classmethod
    def get_color(cls, num: int) -> str:
        """Retorna a cor"""
        if num == 0:
            return 'green'
        return 'red' if num in cls.RED_NUMBERS else 'black'
    
    @classmethod
    def get_parity(cls, num: int) -> str:
        """Retorna a paridade"""
        if num == 0:
            return 'zero'
        return 'even' if num % 2 == 0 else 'odd'
    
    @classmethod
    def get_range(cls, num: int) -> str:
        """Retorna a faixa (baixo/alto)"""
        if num == 0:
            return 'zero'
        return 'low' if num <= 18 else 'high'
    
    @classmethod
    def get_group(cls, num: int) -> str:
        """Retorna o grupo estrutural"""
        if num in cls.VOISINS:
            return 'voisins'
        elif num in cls.TIERS:
            return 'tiers'
        elif num in cls.ORPHELINS:
            return 'orphelins'
        return 'none'
    
    @classmethod
    def get_numbers_by_combined(cls, dozen: int, parity: str) -> Set[int]:
        """Retorna números por propriedade combinada (ex: D1 Par)"""
        numbers = set()
        dozen_start = (dozen - 1) * 12 + 1
        dozen_end = dozen * 12
        
        for num in range(dozen_start, dozen_end + 1):
            if parity == 'even' and num % 2 == 0:
                numbers.add(num)
            elif parity == 'odd' and num % 2 == 1:
                numbers.add(num)
        
        return numbers


@dataclass
class PropertyPattern:
    """Representa um padrão de propriedade detectado"""
    property_type: PropertyType
    pattern: List[Any]  # Sequência de valores da propriedade
    occurrences: int = 0
    last_index: int = -1
    pattern_type: str = ""  # 'alternation', 'repetition', 'progression'
    confidence: float = 0.0
    
    def is_confirmed(self, min_occurrences: int = 2) -> bool:
        """Verifica se o padrão está confirmado"""
        return self.occurrences >= min_occurrences


@dataclass
class CycleDetection:
    """Detecta e armazena ciclos completos"""
    cycle_type: str  # 'dozen', 'column', 'binary', etc
    elements: List[Any]
    completed: bool = False
    break_point: Optional[Any] = None
    next_expected: Optional[Any] = None


class PatternMaster(BasePattern):
    """
    Motor da Análise Master - Propriedades Objetivas
    Detecta padrões através de estruturas fixas e mensuráveis
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Inicializa o Pattern Master
        
        Args:
            config: Dicionário de configurações
                - window_sizes: Dict[PropertyType, int] - janelas por propriedade
                - min_confirmations: Dict[PropertyType, int] - confirmações mínimas
                - enable_combined: bool - habilitar propriedades combinadas
                - enable_blocks: bool - habilitar bloqueios universais
                - cycle_detection: bool - detectar ciclos completos
                - verbose: bool
        """
        super().__init__(config)
        
        # Janelas específicas por propriedade (do manual)
        default_windows = {
            PropertyType.COLOR: 10,
            PropertyType.PARITY: 10,
            PropertyType.DOZEN: 200,
            PropertyType.COLUMN: 200,
            PropertyType.RANGE: 15,
            PropertyType.GROUP: 200,
            PropertyType.COMBINED: 15
        }
        self.window_sizes = self.get_config_value('window_sizes', default_windows)
        
        # Confirmações mínimas por propriedade
        default_confirmations = {
            PropertyType.COLOR: 3,     # 3 repetições ou 2 alternâncias
            PropertyType.PARITY: 3,
            PropertyType.DOZEN: 2,
            PropertyType.COLUMN: 2,
            PropertyType.RANGE: 2,
            PropertyType.GROUP: 2,
            PropertyType.COMBINED: 2
        }
        self.min_confirmations = self.get_config_value('min_confirmations', default_confirmations)
        
        # Configurações
        self.enable_combined = self.get_config_value('enable_combined', True)
        self.enable_blocks = self.get_config_value('enable_blocks', True)
        self.cycle_detection = self.get_config_value('cycle_detection', True)
        self.verbose = self.get_config_value('verbose', False)
        
        # Estruturas de dados
        self.properties = RouletteProperties()
        self.property_history: Dict[PropertyType, deque] = {}
        self.pattern_cache: Dict[str, PropertyPattern] = {}
        self.active_cycles: List[CycleDetection] = []
        self.block_conditions: Set[str] = set()
        
        # Inicializa históricos por propriedade
        for prop_type in PropertyType:
            max_window = max(self.window_sizes.values())
            self.property_history[prop_type] = deque(maxlen=max_window)
        
        # Estatísticas
        self.stats = {
            'patterns_detected': 0,
            'cycles_completed': 0,
            'blocks_triggered': 0,
            'confluences_found': 0
        }
    
    def analyze(self, history: List[int]) -> PatternResult:
        """
        Analisa o histórico através das propriedades objetivas
        
        Args:
            history: Lista de números (mais recente no índice 0)
        
        Returns:
            PatternResult com candidatos baseados em propriedades
        """
        # Valida histórico
        if not self.validate_history(history, min_size=5):
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={'error': 'Histórico inválido ou insuficiente'},
                pattern_name=self.name
            )
        
        # Inverte para processar (Master lê de baixo para cima)
        history_reversed = list(reversed(history))
        
        # Processa propriedades
        self.process_properties(history_reversed)
        
        # Detecta padrões
        patterns = self.detect_property_patterns()
        
        # Detecta ciclos se habilitado
        if self.cycle_detection:
            cycles = self.detect_cycles()
        else:
            cycles = []
        
        # Verifica bloqueios
        if self.enable_blocks:
            self.check_block_conditions()
        
        # Gera candidatos baseado em confluência
        candidates = self.generate_candidates(patterns, cycles)
        
        if not candidates:
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={'reason': 'Nenhuma confluência de propriedades detectada'},
                pattern_name=self.name
            )
        
        # Normaliza scores
        scores = self.normalize_scores(candidates)
        
        # Top candidatos
        sorted_candidates = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_candidates = [num for num, _ in sorted_candidates[:6]]
        
        # Adiciona zero como proteção se não estiver
        if 0 not in top_candidates:
            top_candidates.append(0)
        
        # Metadata
        metadata = {
            'patterns_detected': len(patterns),
            'cycles_active': len(cycles),
            'blocks_active': len(self.block_conditions),
            'confluences': self.stats['confluences_found'],
            'strongest_pattern': self._get_strongest_pattern(patterns),
            'reason': self._generate_reason(patterns, cycles)
        }
        
        return PatternResult(
            candidatos=top_candidates[:6],
            scores=scores,
            metadata=metadata,
            pattern_name=self.name
        )
    
    def process_properties(self, history: List[int]) -> None:
        """Processa o histórico extraindo todas as propriedades"""
        # Limpa históricos
        for prop_history in self.property_history.values():
            prop_history.clear()
        
        # Processa cada número
        for num in history:
            props = self.properties.get_all_properties(num)
            
            # Adiciona cada propriedade ao seu histórico
            self.property_history[PropertyType.DOZEN].append(props['dozen'])
            self.property_history[PropertyType.COLUMN].append(props['column'])
            self.property_history[PropertyType.COLOR].append(props['color'])
            self.property_history[PropertyType.PARITY].append(props['parity'])
            self.property_history[PropertyType.RANGE].append(props['range'])
            self.property_history[PropertyType.GROUP].append(props['group'])
            
            if self.enable_combined:
                self.property_history[PropertyType.COMBINED].append(props['combined'])
    
    def detect_property_patterns(self) -> List[PropertyPattern]:
        """Detecta padrões em cada propriedade"""
        patterns = []
        self.pattern_cache.clear()
        
        for prop_type, history in self.property_history.items():
            if len(history) < 3:
                continue
            
            # Pega janela específica para esta propriedade
            window_size = self.window_sizes.get(prop_type, 10)
            window = list(history)[-window_size:] if len(history) > window_size else list(history)
            
            # Detecta alternâncias
            alternation = self._detect_alternation(window, prop_type)
            if alternation and alternation.is_confirmed(self.min_confirmations[prop_type]):
                patterns.append(alternation)
                self.pattern_cache[f"{prop_type}_alternation"] = alternation
            
            # Detecta repetições
            repetition = self._detect_repetition(window, prop_type)
            if repetition and repetition.is_confirmed(self.min_confirmations[prop_type]):
                patterns.append(repetition)
                self.pattern_cache[f"{prop_type}_repetition"] = repetition
            
            # Detecta progressões (para dúzia e coluna)
            if prop_type in [PropertyType.DOZEN, PropertyType.COLUMN]:
                progression = self._detect_progression(window, prop_type)
                if progression and progression.is_confirmed(2):
                    patterns.append(progression)
                    self.pattern_cache[f"{prop_type}_progression"] = progression
        
        self.stats['patterns_detected'] = len(patterns)
        return patterns
    
    def _detect_alternation(self, window: List[Any], prop_type: PropertyType) -> Optional[PropertyPattern]:
        """Detecta padrões de alternância"""
        if len(window) < 4:
            return None
        
        # Conta alternâncias
        alternations = 0
        pattern = []
        
        for i in range(len(window) - 1):
            if window[i] != window[i + 1]:
                alternations += 1
                if not pattern or pattern[-1] != window[i]:
                    pattern.append(window[i])
        
        # Se há alternância consistente
        if alternations >= len(window) - 2:  # Quase todos alternando
            return PropertyPattern(
                property_type=prop_type,
                pattern=pattern[-4:],  # Últimos 4 elementos
                occurrences=alternations // 2,
                last_index=len(window) - 1,
                pattern_type='alternation',
                confidence=alternations / (len(window) - 1)
            )
        
        return None
    
    def _detect_repetition(self, window: List[Any], prop_type: PropertyType) -> Optional[PropertyPattern]:
        """Detecta padrões de repetição"""
        if len(window) < 3:
            return None
        
        # Conta repetições consecutivas
        counter = Counter()
        current = window[-1]
        count = 1
        pattern = []
        
        for i in range(len(window) - 2, -1, -1):
            if window[i] == current:
                count += 1
            else:
                if count >= 2:
                    counter[current] = count
                    pattern.append((current, count))
                current = window[i]
                count = 1
        
        if count >= 2:
            counter[current] = count
            pattern.append((current, count))
        
        # Se há repetições significativas
        if counter:
            most_common = counter.most_common(1)[0]
            return PropertyPattern(
                property_type=prop_type,
                pattern=[most_common[0]],
                occurrences=most_common[1],
                last_index=len(window) - 1,
                pattern_type='repetition',
                confidence=most_common[1] / len(window)
            )
        
        return None
    
    def _detect_progression(self, window: List[Any], prop_type: PropertyType) -> Optional[PropertyPattern]:
        """Detecta progressões (D1→D2→D3 ou C1→C2→C3)"""
        if len(window) < 3:
            return None
        
        progressions = []
        
        # Busca por progressões crescentes ou decrescentes
        for i in range(len(window) - 2):
            seq = window[i:i + 3]
            
            # Ignora zeros
            seq = [x for x in seq if x != 0]
            if len(seq) < 3:
                continue
            
            # Verifica se é progressão
            if seq == [1, 2, 3] or seq == [3, 2, 1]:  # Progressão de dúzia/coluna
                progressions.append(tuple(seq))
            elif all(seq[i] < seq[i + 1] for i in range(len(seq) - 1)):  # Crescente
                progressions.append(tuple(seq))
            elif all(seq[i] > seq[i + 1] for i in range(len(seq) - 1)):  # Decrescente
                progressions.append(tuple(seq))
        
        if progressions:
            most_common = Counter(progressions).most_common(1)[0]
            return PropertyPattern(
                property_type=prop_type,
                pattern=list(most_common[0]),
                occurrences=most_common[1],
                last_index=len(window) - 1,
                pattern_type='progression',
                confidence=most_common[1] / len(progressions) if progressions else 0
            )
        
        return None
    
    def detect_cycles(self) -> List[CycleDetection]:
        """Detecta ciclos completos"""
        cycles = []
        
        # Ciclo de dúzias (D1→D2→D3)
        dozen_history = list(self.property_history[PropertyType.DOZEN])[-9:]
        if len(dozen_history) >= 3:
            # Remove zeros
            dozen_clean = [d for d in dozen_history if d != 0]
            if len(dozen_clean) >= 3:
                # Verifica se passou por todas as dúzias
                last_3_unique = set(dozen_clean[-3:])
                if last_3_unique == {1, 2, 3}:
                    cycle = CycleDetection(
                        cycle_type='dozen_complete',
                        elements=dozen_clean[-3:],
                        completed=True,
                        next_expected=dozen_clean[-3]  # Volta ao início
                    )
                    cycles.append(cycle)
        
        # Ciclo binário (repetições de 2)
        color_history = list(self.property_history[PropertyType.COLOR])[-6:]
        if len(color_history) >= 6:
            # Verifica padrão PP-VV-PP ou VV-PP-VV
            pattern = []
            i = 0
            while i < len(color_history) - 1:
                if color_history[i] == color_history[i + 1]:
                    pattern.append((color_history[i], 2))
                    i += 2
                else:
                    i += 1
            
            if len(pattern) >= 2 and pattern[-1][0] != pattern[-2][0]:
                cycle = CycleDetection(
                    cycle_type='binary_color',
                    elements=[p[0] for p in pattern],
                    completed=len(pattern) >= 3,
                    next_expected='red' if pattern[-1][0] == 'black' else 'black'
                )
                cycles.append(cycle)
        
        # Ciclo de paridade com quebra
        parity_history = list(self.property_history[PropertyType.PARITY])[-5:]
        if len(parity_history) >= 3:
            # Conta repetições consecutivas
            last_parity = parity_history[-1]
            consecutive = 1
            for i in range(len(parity_history) - 2, -1, -1):
                if parity_history[i] == last_parity:
                    consecutive += 1
                else:
                    break
            
            if consecutive >= 3:  # Ponto de quebra
                cycle = CycleDetection(
                    cycle_type='parity_break',
                    elements=parity_history[-3:],
                    completed=False,
                    break_point=last_parity,
                    next_expected='odd' if last_parity == 'even' else 'even'
                )
                cycles.append(cycle)
        
        self.stats['cycles_completed'] = sum(1 for c in cycles if c.completed)
        self.active_cycles = cycles
        return cycles
    
    def check_block_conditions(self) -> None:
        """Verifica condições de bloqueio universal"""
        self.block_conditions.clear()
        
        # Bloqueio 1: Repetição de cor/paridade >3 (ciclo exausto)
        for prop_type in [PropertyType.COLOR, PropertyType.PARITY]:
            history = list(self.property_history[prop_type])[-4:]
            if len(history) == 4 and len(set(history)) == 1:
                self.block_conditions.add(f"{prop_type.value}_exhausted")
                self.stats['blocks_triggered'] += 1
        
        # Bloqueio 2: Alternância não confirmada historicamente
        # (Simplificado - em produção verificaria histórico completo)
        for pattern in self.pattern_cache.values():
            if pattern.pattern_type == 'alternation' and pattern.confidence < 0.5:
                self.block_conditions.add(f"{pattern.property_type.value}_unconfirmed")
                self.stats['blocks_triggered'] += 1
    
    def generate_candidates(self, patterns: List[PropertyPattern], 
                          cycles: List[CycleDetection]) -> Dict[int, float]:
        """Gera candidatos baseado em confluência de propriedades"""
        candidates = defaultdict(float)
        
        # Para cada padrão confirmado
        for pattern in patterns:
            weight = pattern.confidence
            numbers = self._get_numbers_for_pattern(pattern)
            
            for num in numbers:
                # Aplica bloqueios
                if not self._is_blocked(num):
                    candidates[num] += weight
        
        # Para cada ciclo ativo
        for cycle in cycles:
            if cycle.next_expected:
                numbers = self._get_numbers_for_cycle(cycle)
                weight = 0.8 if cycle.completed else 0.5
                
                for num in numbers:
                    if not self._is_blocked(num):
                        candidates[num] += weight
        
        # Verifica confluências (múltiplas propriedades apontando mesmo número)
        confluences = defaultdict(int)
        for pattern in patterns:
            numbers = self._get_numbers_for_pattern(pattern)
            for num in numbers:
                confluences[num] += 1
        
        # Bônus por confluência
        for num, count in confluences.items():
            if count >= 2:  # Pelo menos 2 propriedades convergindo
                candidates[num] *= (1 + count * 0.2)
                self.stats['confluences_found'] += 1
        
        # Adiciona zero como proteção
        if 0 not in candidates:
            candidates[0] = 0.1
        
        return dict(candidates)
    
    def _get_numbers_for_pattern(self, pattern: PropertyPattern) -> Set[int]:
        """Retorna números que satisfazem o padrão"""
        numbers = set()
        prop_type = pattern.property_type
        
        if pattern.pattern_type == 'alternation':
            # Próximo da alternância
            next_value = pattern.pattern[0] if len(pattern.pattern) % 2 == 0 else pattern.pattern[-1]
        elif pattern.pattern_type == 'repetition':
            # Mantém repetição
            next_value = pattern.pattern[0]
        elif pattern.pattern_type == 'progression':
            # Próximo da progressão
            if pattern.pattern == [1, 2, 3]:
                next_value = 1  # Volta ao início
            elif pattern.pattern == [3, 2, 1]:
                next_value = 3  # Volta ao início
            else:
                next_value = pattern.pattern[-1]
        else:
            return numbers
        
        # Converte valor em números
        if prop_type == PropertyType.DOZEN:
            for num in range(1, 37):
                if self.properties.get_dozen(num) == next_value:
                    numbers.add(num)
        elif prop_type == PropertyType.COLUMN:
            for num in range(1, 37):
                if self.properties.get_column(num) == next_value:
                    numbers.add(num)
        elif prop_type == PropertyType.COLOR:
            if next_value == 'red':
                numbers.update(self.properties.RED_NUMBERS)
            elif next_value == 'black':
                numbers.update(self.properties.BLACK_NUMBERS)
        elif prop_type == PropertyType.PARITY:
            for num in range(1, 37):
                if self.properties.get_parity(num) == next_value:
                    numbers.add(num)
        elif prop_type == PropertyType.RANGE:
            if next_value == 'low':
                numbers.update(range(1, 19))
            elif next_value == 'high':
                numbers.update(range(19, 37))
        elif prop_type == PropertyType.GROUP:
            if next_value == 'voisins':
                numbers.update(self.properties.VOISINS)
            elif next_value == 'tiers':
                numbers.update(self.properties.TIERS)
            elif next_value == 'orphelins':
                numbers.update(self.properties.ORPHELINS)
        elif prop_type == PropertyType.COMBINED:
            # Exemplo: D1P = Dúzia 1 Par
            if len(next_value) >= 3 and next_value[0] == 'D':
                dozen = int(next_value[1])
                parity = 'even' if next_value[2] == 'E' else 'odd'
                numbers.update(self.properties.get_numbers_by_combined(dozen, parity))
        
        return numbers
    
    def _get_numbers_for_cycle(self, cycle: CycleDetection) -> Set[int]:
        """Retorna números esperados para um ciclo"""
        numbers = set()
        
        if cycle.cycle_type == 'dozen_complete' and cycle.next_expected:
            # Retorna à dúzia inicial
            for num in range(1, 37):
                if self.properties.get_dozen(num) == cycle.next_expected:
                    numbers.add(num)
        
        elif cycle.cycle_type == 'binary_color' and cycle.next_expected:
            # Próxima cor do padrão binário
            if cycle.next_expected == 'red':
                numbers.update(self.properties.RED_NUMBERS)
            elif cycle.next_expected == 'black':
                numbers.update(self.properties.BLACK_NUMBERS)
        
        elif cycle.cycle_type == 'parity_break' and cycle.next_expected:
            # Quebra de paridade
            for num in range(1, 37):
                if self.properties.get_parity(num) == cycle.next_expected:
                    # Adiciona apenas números da dúzia inicial
                    if self.properties.get_dozen(num) == 1:  # D1 após quebra
                        numbers.add(num)
        
        return numbers
    
    def _is_blocked(self, num: int) -> bool:
        """Verifica se um número está bloqueado"""
        if not self.enable_blocks:
            return False
        
        props = self.properties.get_all_properties(num)
        
        # Verifica cada condição de bloqueio
        for block in self.block_conditions:
            if 'color_exhausted' in block and props['color'] in ['red', 'black']:
                return True
            if 'parity_exhausted' in block and props['parity'] in ['even', 'odd']:
                return True
        
        return False
    
    def _get_strongest_pattern(self, patterns: List[PropertyPattern]) -> Dict[str, Any]:
        """Retorna o padrão mais forte detectado"""
        if not patterns:
            return {}
        
        strongest = max(patterns, key=lambda p: p.confidence * p.occurrences)
        
        return {
            'type': strongest.property_type.value,
            'pattern': strongest.pattern,
            'confidence': strongest.confidence,
            'occurrences': strongest.occurrences
        }
    
    def _generate_reason(self, patterns: List[PropertyPattern], 
                        cycles: List[CycleDetection]) -> str:
        """Gera explicação da análise"""
        reasons = []
        
        # Padrões mais fortes
        for pattern in sorted(patterns, key=lambda p: p.confidence, reverse=True)[:2]:
            if pattern.pattern_type == 'alternation':
                reasons.append(f"Alternância {pattern.property_type.value} confirmada")
            elif pattern.pattern_type == 'repetition':
                reasons.append(f"Repetição {pattern.property_type.value} {pattern.occurrences}x")
            elif pattern.pattern_type == 'progression':
                reasons.append(f"Progressão {pattern.property_type.value} detectada")
        
        # Ciclos ativos
        for cycle in cycles[:1]:
            if cycle.completed:
                reasons.append(f"Ciclo {cycle.cycle_type} completo")
            elif cycle.break_point:
                reasons.append(f"Quebra de {cycle.cycle_type} em {cycle.break_point}")
        
        # Bloqueios ativos
        if self.block_conditions:
            reasons.append(f"{len(self.block_conditions)} bloqueios ativos")
        
        return " | ".join(reasons) if reasons else "Análise de propriedades objetivas"