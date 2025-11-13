"""
patterns/pattern_estelar.py

🔱 ANÁLISE ESTELAR - Pattern Recognition Module
Sistema de reconhecimento de padrões equivalentes através de trincas comportamentais.
Detecta repetições não-literais usando substituições hierárquicas e ressonância tripla.
"""

from typing import Dict, List, Tuple, Set, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from datetime import datetime
from enum import Enum
import logging

# Importa a classe base
from patterns.base import BasePattern, PatternResult

logger = logging.getLogger(__name__)


class EquivalenceType(Enum):
    """Tipos de equivalência em ordem hierárquica"""
    EXACT = 1.0      # Número exato
    NEIGHBOR = 0.8   # Vizinho no cilindro (1 passo)
    TERMINAL = 0.6   # Mesmo terminal (último dígito)
    MIRROR = 0.5     # Espelho fixo
    PROPERTY = 0.4   # Propriedades (cor/dúzia/coluna/paridade)
    BEHAVIORAL = 0.3 # Comportamental (soma/dobro/metade)


class RouletteRelations:
    """Relações e equivalências da roleta europeia"""
    
    # Ordem dos números no cilindro europeu
    WHEEL_ORDER = [0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26]
    
    # Espelhos fixos
    MIRRORS = {
        1: 10, 10: 1,
        2: 20, 20: 2,
        3: 30, 30: 3,
        6: 9, 9: 6,
        16: 19, 19: 16,
        26: 29, 29: 26,
        13: 31, 31: 13,
        12: 21, 21: 12,
        32: 23, 23: 32
    }
    
    # Cores
    RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
    BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}
    
    @classmethod
    def get_neighbors(cls, num: int, distance: int = 1) -> Set[int]:
        """Retorna vizinhos no cilindro com distância especificada"""
        if num == 0:
            return {32, 26} if distance == 1 else set()
        
        # Valida se número está na roleta
        if num not in cls.WHEEL_ORDER:
            return set()
        
        idx = cls.WHEEL_ORDER.index(num)
        neighbors = set()
        
        for d in range(1, distance + 1):
            left_idx = (idx - d) % len(cls.WHEEL_ORDER)
            right_idx = (idx + d) % len(cls.WHEEL_ORDER)
            neighbors.add(cls.WHEEL_ORDER[left_idx])
            neighbors.add(cls.WHEEL_ORDER[right_idx])
        
        return neighbors - {0}  # Remove o zero dos vizinhos
    
    @classmethod
    def get_terminal(cls, num: int) -> int:
        """Retorna o terminal (último dígito)"""
        return num % 10 if num > 0 else -1
    
    @classmethod
    def get_terminal_family(cls, num: int) -> Set[int]:
        """Retorna família do terminal"""
        if num == 0:
            return {0}
        terminal = num % 10
        return {n for n in range(terminal, 37, 10) if n > 0}
    
    @classmethod
    def get_mirror(cls, num: int) -> Optional[int]:
        """Retorna o espelho do número"""
        return cls.MIRRORS.get(num)
    
    @classmethod
    def get_properties(cls, num: int) -> Dict[str, any]:
        """Retorna propriedades do número"""
        if num == 0:
            return {'color': 'green', 'dozen': 0, 'column': 0, 'parity': 'zero', 'half': 'zero'}
        
        return {
            'color': 'red' if num in cls.RED_NUMBERS else 'black',
            'dozen': (num - 1) // 12 + 1,
            'column': ((num - 1) % 3) + 1,
            'parity': 'even' if num % 2 == 0 else 'odd',
            'half': 'low' if num <= 18 else 'high'
        }
    
    @classmethod
    def get_behavioral_equivalents(cls, num: int) -> Set[int]:
        """Retorna equivalentes comportamentais (soma, dobro, metade)"""
        if num == 0:
            return {0}
        
        equivalents = set()
        
        # Soma dos dígitos
        digit_sum = sum(int(d) for d in str(num))
        for n in range(1, 37):
            if sum(int(d) for d in str(n)) == digit_sum:
                equivalents.add(n)
        
        # Dobro e metade
        if num * 2 <= 36:
            equivalents.add(num * 2)
        if num % 2 == 0:
            equivalents.add(num // 2)
        
        return equivalents - {num}


@dataclass
class Trinca:
    """Representa uma trinca de números com suas ocorrências"""
    pattern: Tuple[int, int, int]  # (A, B, C)
    occurrences: List[Dict] = field(default_factory=list)
    last_occurrence_idx: int = -1
    confidence_level: int = 0
    equivalence_type: EquivalenceType = EquivalenceType.EXACT
    
    def add_occurrence(self, idx: int, gap_pattern: str, timestamp: datetime = None):
        """Adiciona uma ocorrência da trinca"""
        self.occurrences.append({
            'index': idx,
            'gap_pattern': gap_pattern,
            'timestamp': timestamp or datetime.now()
        })
        self.last_occurrence_idx = idx
    
    @property
    def occurrence_count(self) -> int:
        return len(self.occurrences)
    
    @property
    def is_active(self) -> bool:
        """Trinca ativa se tem pelo menos 2 ocorrências"""
        return self.occurrence_count >= 2


class PatternEstelar(BasePattern):
    """
    Motor da Análise Estelar seguindo o padrão base do projeto
    Detecta trincas com equivalências e calcula predições baseadas em ressonância
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Inicializa o padrão Estelar
        
        Args:
            config: Dicionário de configurações
                - max_gap_between_elements: int (default: 2)
                - memory_short: int (default: 10)
                - memory_long: int (default: 200)
                - min_occurrences: int (default: 2)
                - equivalence_weights: Dict[str, float]
                - pillar_weights: Dict[int, float]
                - enable_inversions: bool (default: True)
                - enable_compensation: bool (default: True)
                - verbose: bool (default: False)
        """
        super().__init__(config)
        
        # Configurações específicas do Estelar
        self.max_gap_between_elements = self.get_config_value('max_gap_between_elements', 2)
        self.memory_short = self.get_config_value('memory_short', 10)
        self.memory_long = self.get_config_value('memory_long', 200)
        self.min_occurrences = self.get_config_value('min_occurrences', 2)
        
        # Pesos das equivalências
        default_equiv_weights = {
            'EXACT': 1.0,
            'NEIGHBOR': 0.8,
            'TERMINAL': 0.6,
            'MIRROR': 0.5,
            'PROPERTY': 0.4,
            'BEHAVIORAL': 0.3
        }
        self.equivalence_weights = self.get_config_value('equivalence_weights', default_equiv_weights)
        
        # Pesos dos pilares
        default_pillar_weights = {
            3: 1.0,  # Alta confiança (3 pilares)
            2: 0.7,  # Média confiança
            1: 0.4,  # Baixa confiança
            0: 0.0   # Sem entrada
        }
        self.pillar_weights = self.get_config_value('pillar_weights', default_pillar_weights)
        
        # Comportamento
        self.enable_inversions = self.get_config_value('enable_inversions', True)
        self.enable_compensation = self.get_config_value('enable_compensation', True)
        self.verbose = self.get_config_value('verbose', False)
        
        # Inicializa relações e cache
        self.relations = RouletteRelations()
        self.trinca_cache: Dict[Tuple, List[Trinca]] = defaultdict(list)
        self.processed_history: List[int] = []
        
        # Estatísticas
        self.stats = {
            'trincas_found': 0,
            'active_trincas': 0,
            'predictions_made': 0,
            'hits': 0
        }
    
    def analyze(self, history: List[int]) -> PatternResult:
        """
        Analisa o histórico e retorna candidatos seguindo o padrão base
        
        Args:
            history: Lista de números (mais recente no índice 0)
        
        Returns:
            PatternResult com candidatos, scores e metadata
        """
        # Valida histórico
        if not self.validate_history(history, min_size=10):
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={'error': 'Histórico inválido ou insuficiente'},
                pattern_name=self.name
            )
        
        # Inverte para processar (Estelar processa antigo→recente)
        history_reversed = list(reversed(history[:self.memory_long]))
        
        # Processa histórico para identificar trincas
        self.process_history(history_reversed)
        
        # Detecta ressonância
        predictions = self.detect_resonance(history_reversed)
        
        if not predictions:
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={'reason': 'Nenhuma ressonância detectada'},
                pattern_name=self.name
            )
        
        # Pega melhor predição
        best_prediction = predictions[0]
        
        # Converte candidatos para formato do PatternResult
        scores = {}
        candidatos = []
        
        for num, weight in best_prediction['candidates']:
            if 0 <= num <= 36 and num not in scores:
                scores[num] = weight * best_prediction['score']
                candidatos.append(num)
        
        # Adiciona zero como proteção se não estiver
        if 0 not in scores:
            scores[0] = 0.1  # Score baixo para zero (proteção)
            candidatos.append(0)
        
        # Normaliza scores
        scores = self.normalize_scores(scores)
        
        # Metadata
        metadata = {
            'trinca': best_prediction.get('trinca', []),
            'confidence': best_prediction.get('confidence', 0),
            'occurrences': best_prediction.get('occurrences', 0),
            'reason': best_prediction.get('reason', ''),
            'active_trincas': self.stats['active_trincas'],
            'trincas_found': self.stats['trincas_found']
        }
        
        return PatternResult(
            candidatos=candidatos[:6],  # Top 6 candidatos
            scores=scores,
            metadata=metadata,
            pattern_name=self.name
        )
    
    def extract_trincas_with_gaps(self, history: List[int]) -> List[Tuple[Tuple[int, int, int], str, int]]:
        """
        Extrai todas as trincas possíveis com gaps configuráveis
        Returns: Lista de (trinca, gap_pattern, start_index)
        """
        trincas = []
        max_gap = self.max_gap_between_elements
        
        for start_idx in range(len(history) - 2):
            # Elemento A
            a = history[start_idx]
            
            # Procura B com possíveis gaps
            for b_offset in range(1, min(max_gap + 2, len(history) - start_idx - 1)):
                b_idx = start_idx + b_offset
                b = history[b_idx]
                
                # Procura C com possíveis gaps após B
                for c_offset in range(1, min(max_gap + 2, len(history) - b_idx)):
                    c_idx = b_idx + c_offset
                    c = history[c_idx]
                    
                    # Cria padrão de gaps
                    gap_a_b = b_offset - 1
                    gap_b_c = c_offset - 1
                    gap_pattern = f"A{'-X' * gap_a_b}-B{'-X' * gap_b_c}-C"
                    
                    trincas.append(((a, b, c), gap_pattern, start_idx))
        
        return trincas
    
    def normalize_trinca(self, trinca: Tuple[int, int, int]) -> List[Tuple[Tuple[int, int, int], str, float]]:
        """
        Normaliza uma trinca gerando todas as equivalências válidas
        Returns: Lista de (trinca_normalizada, tipo_equivalencia_str, peso)
        """
        a, b, c = trinca
        normalized = []
        
        # Valida números
        valid_numbers = set(range(0, 37))
        if not all(n in valid_numbers for n in trinca):
            return [(trinca, 'EXACT', 1.0)]
        
        # 1. Exato
        normalized.append((trinca, 'EXACT', 1.0))
        
        # 2. Vizinhos
        if self.equivalence_weights.get('NEIGHBOR', 0) > 0:
            neighbors_a = list(self.relations.get_neighbors(a, 1))
            neighbors_b = list(self.relations.get_neighbors(b, 1))
            neighbors_c = list(self.relations.get_neighbors(c, 1))
            
            for na in [a] + neighbors_a:
                for nb in [b] + neighbors_b:
                    for nc in [c] + neighbors_c:
                        if (na, nb, nc) != trinca:
                            normalized.append(((na, nb, nc), 'NEIGHBOR', 
                                             self.equivalence_weights['NEIGHBOR']))
        
        # 3. Terminal
        if self.equivalence_weights.get('TERMINAL', 0) > 0:
            terminals = [self.relations.get_terminal(n) for n in trinca]
            if terminals.count(terminals[0]) >= 2:  # Pelo menos 2 iguais
                for ta in self.relations.get_terminal_family(a):
                    for tb in self.relations.get_terminal_family(b):
                        for tc in self.relations.get_terminal_family(c):
                            if (ta, tb, tc) != trinca:
                                normalized.append(((ta, tb, tc), 'TERMINAL',
                                                 self.equivalence_weights['TERMINAL']))
        
        # 4. Espelhos
        if self.equivalence_weights.get('MIRROR', 0) > 0:
            ma = self.relations.get_mirror(a) or a
            mb = self.relations.get_mirror(b) or b
            mc = self.relations.get_mirror(c) or c
            if (ma, mb, mc) != trinca:
                normalized.append(((ma, mb, mc), 'MIRROR',
                                 self.equivalence_weights['MIRROR']))
        
        # 5. Inversões
        if self.enable_inversions and self.equivalence_weights.get('BEHAVIORAL', 0) > 0:
            inversions = [
                (b, a, c),  # Inverte A-B
                (a, c, b),  # Inverte B-C
                (c, b, a)   # Inverte total
            ]
            for inv in inversions:
                if inv != trinca:
                    normalized.append((inv, 'BEHAVIORAL', 
                                     self.equivalence_weights['BEHAVIORAL']))
        
        return normalized
    
    def calculate_pillar_strength(self, original: Tuple[int, int, int], 
                                 candidate: Tuple[int, int, int]) -> int:
        """Calcula quantos pilares (Exato/Terminal/Vizinho) confirmam"""
        pillars = 0
        
        # Pilar 1: Exato
        exact_matches = sum(1 for i in range(3) if original[i] == candidate[i])
        if exact_matches >= 2:
            pillars += 1
        
        # Pilar 2: Terminal
        orig_terminals = [self.relations.get_terminal(n) for n in original]
        cand_terminals = [self.relations.get_terminal(n) for n in candidate]
        terminal_matches = sum(1 for i in range(3) if orig_terminals[i] == cand_terminals[i])
        if terminal_matches >= 2:
            pillars += 1
        
        # Pilar 3: Vizinho
        neighbor_matches = 0
        for i in range(3):
            if candidate[i] in self.relations.get_neighbors(original[i], 1) or candidate[i] == original[i]:
                neighbor_matches += 1
        if neighbor_matches >= 2:
            pillars += 1
        
        return pillars
    
    def process_history(self, history: List[int]) -> None:
        """Processa o histórico e identifica todas as trincas ativas"""
        self.processed_history = history.copy()
        self.trinca_cache.clear()
        
        # Extrai todas as trincas com gaps
        all_trincas = self.extract_trincas_with_gaps(history)
        
        # Agrupa trincas equivalentes
        trinca_groups = defaultdict(list)
        
        for trinca, gap_pattern, idx in all_trincas:
            # Gera todas as normalizações
            normalized_versions = self.normalize_trinca(trinca)
            
            for norm_trinca, equiv_type_str, weight in normalized_versions:
                # Cria chave canônica
                canonical = tuple(sorted(norm_trinca))
                
                # Adiciona ocorrência
                found = False
                for existing in trinca_groups[canonical]:
                    if existing.pattern == norm_trinca:
                        existing.add_occurrence(idx, gap_pattern)
                        found = True
                        break
                
                if not found:
                    # Converte string para Enum
                    equiv_type = EquivalenceType[equiv_type_str]
                    new_trinca = Trinca(norm_trinca, equivalence_type=equiv_type)
                    new_trinca.add_occurrence(idx, gap_pattern)
                    trinca_groups[canonical].append(new_trinca)
        
        # Filtra apenas trincas ativas
        for canonical, trinca_list in trinca_groups.items():
            active_trincas = [t for t in trinca_list if t.is_active]
            if active_trincas:
                # Calcula força dos pilares
                for trinca in active_trincas:
                    if len(trinca.occurrences) >= 2:
                        trinca.confidence_level = self.calculate_pillar_strength(
                            trinca.pattern, trinca.pattern
                        )
                
                self.trinca_cache[canonical] = active_trincas
        
        # Atualiza estatísticas
        self.stats['trincas_found'] = sum(len(v) for v in trinca_groups.values())
        self.stats['active_trincas'] = len(self.trinca_cache)
        
        if self.verbose:
            logger.info(f"Processado: {self.stats['trincas_found']} trincas, "
                       f"{self.stats['active_trincas']} ativas")
    
    def detect_resonance(self, recent_numbers: List[int]) -> List[Dict]:
        """Detecta ressonância - quando A e B de uma trinca ativa aparecem"""
        if len(recent_numbers) < 2:
            return []
        
        predictions = []
        recent_window = recent_numbers[-self.memory_short:]
        
        # Para cada trinca ativa
        for canonical, trinca_list in self.trinca_cache.items():
            for trinca in trinca_list:
                if not trinca.is_active:
                    continue
                
                a, b, c = trinca.pattern
                
                # Verifica se A e B estão na janela recente
                if a in recent_window and b in recent_window:
                    # Calcula recência
                    a_idx = len(recent_window) - 1 - recent_window[::-1].index(a)
                    b_idx = len(recent_window) - 1 - recent_window[::-1].index(b)
                    recency = (a_idx + b_idx) / (2 * len(recent_window))
                    
                    # Calcula score base
                    base_score = (
                        self.pillar_weights.get(trinca.confidence_level, 0) * 
                        self.equivalence_weights.get(trinca.equivalence_type.name, 0.5) *
                        recency
                    )
                    
                    # Gera candidatos
                    candidates = self._get_candidates_for_c(c, trinca)
                    
                    predictions.append({
                        'trinca': trinca.pattern,
                        'missing': c,
                        'candidates': candidates,
                        'score': base_score,
                        'confidence': trinca.confidence_level,
                        'occurrences': trinca.occurrence_count,
                        'type': 'estelar_resonance',
                        'reason': f"Ressonância: {a}-{b}-? (falta {c})"
                    })
        
        # Se múltiplas trincas, pega a mais recente
        if predictions:
            predictions.sort(key=lambda x: x['score'], reverse=True)
            if len(predictions) > 1 and not self.verbose:
                predictions = [predictions[0]]  # Retorna apenas a mais forte
        
        self.stats['predictions_made'] += len(predictions)
        return predictions
    
    def _get_candidates_for_c(self, c: int, trinca: Trinca) -> List[Tuple[int, float]]:
        """Gera candidatos para o número C faltante com seus pesos"""
        candidates = [(c, 1.0)]  # Número exato
        
        # Adiciona equivalentes por prioridade
        # Vizinhos
        for neighbor in self.relations.get_neighbors(c, 1):
            candidates.append((neighbor, 0.8))
        
        # Terminal
        for terminal in self.relations.get_terminal_family(c):
            if terminal != c:
                candidates.append((terminal, 0.6))
        
        # Espelho
        mirror = self.relations.get_mirror(c)
        if mirror:
            candidates.append((mirror, 0.5))
        
        # Compensação comportamental
        if self.enable_compensation:
            behavioral = self.relations.get_behavioral_equivalents(c)
            for equiv in behavioral:
                candidates.append((equiv, 0.3))
        
        # Remove duplicados mantendo maior peso
        seen = {}
        for num, weight in candidates:
            if num not in seen or weight > seen[num]:
                seen[num] = weight
        
        return sorted(seen.items(), key=lambda x: x[1], reverse=True)
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas da análise"""
        total = self.stats['predictions_made']
        hits = self.stats['hits']
        
        return {
            **self.stats,
            'accuracy': hits / total if total > 0 else 0,
            'active_patterns': len(self.trinca_cache)
        }