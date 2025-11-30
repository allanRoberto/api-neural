"""
patterns/chain.py

Padrão CHAIN - Análise Contextual de Fluxo Comportamental

Aprende cadeias dinâmicas (X → Y) em tempo real e identifica
os "faltantes" - números que a mesa ainda deve pagar para fechar ciclos.

Casos de referência:
1. 5-33: Inversão comportamental
2. 7 órfãos: Confirmação tripla
3. 10-20-11 → 7-22-29 → 18: Cadeia aritmética

Autor: Sistema Analizer Master + Estelar
Data: 2025-10-18
"""

from typing import List, Dict, Tuple, Optional, Set, Any
from collections import defaultdict, Counter
from dataclasses import dataclass
import logging

from patterns.base import BasePattern, PatternResult
from utils.constants import ESPELHOS
from utils.helpers import get_vizinhos

logger = logging.getLogger(__name__)


@dataclass
class ChainPattern:
    """Representa um padrão de cadeia aprendido"""
    sequence: Tuple[int, ...]  # Ex: (10, 20, 11)
    outcome: int               # Ex: 7
    count: int                 # Quantas vezes ocorreu
    last_seen: int             # Índice da última ocorrência
    confidence: float          # Confiança calculada


class ChainAnalyzer(BasePattern):
    """
    Padrão CHAIN - Minerador Dinâmico de Cadeias Comportamentais
    
    NÃO usa regras fixas - aprende online a partir do histórico.
    Identifica:
    - Cadeias de puxadas (10→22, 11→7, etc)
    - Faltantes (números que devem pagar)
    - Inversões (33→5 depois 5→33)
    - Compensações (vizinhos/espelhos faltantes)
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Inicializa o analisador CHAIN
        
        Args:
            config: Dicionário de configurações, pode conter:
                - min_chain_support: Mínimo de ocorrências (default: 2)
                - chain_decay: Decaimento temporal (default: 0.95)
                - recent_window_miss: Janela para faltantes (default: 30)
                - max_chain_length: Tamanho máximo da cadeia (default: 4)
        """
        super().__init__(config)
        
        self.min_support = self.get_config_value('min_chain_support', 2)
        self.decay = self.get_config_value('chain_decay', 0.95)
        self.miss_window = self.get_config_value('recent_window_miss', 30)
        self.max_length = self.get_config_value('max_chain_length', 4)
        
        # Armazena cadeias: {comprimento: {sequência: [ChainPattern]}}
        self.chains: Dict[int, Dict[Tuple, List[ChainPattern]]] = defaultdict(lambda: defaultdict(list))
        
        # Cache de pares X→Y simples
        self.pair_cache: Dict[int, Counter] = defaultdict(Counter)
        
        logger.info(
            f"ChainAnalyzer inicializado: support={self.min_support}, "
            f"decay={self.decay}, miss_window={self.miss_window}"
        )
    
    def analyze(self, history: List[int]) -> PatternResult:
        """
        Analisa histórico e retorna candidatos baseados em cadeias
        
        Args:
            history: Lista de números (mais recente primeiro - índice 0)
        
        Returns:
            PatternResult com candidatos, scores e metadata
        """
        if not self.validate_history(history, min_size=self.min_support):
            logger.warning(f"Histórico insuficiente: {len(history)} números")
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={
                    "status": "insuficiente",
                    "motivo": f"Mínimo {self.min_support} números necessários",
                    "total_numeros": len(history)
                },
                pattern_name="chain"
            )
        
        # 1. Aprende do histórico
        self._learn_from_history(history)
        
        # 2. Encontra candidatos e calcula scores
        candidates_scores = self._find_candidates(history[:50])
        
        # 3. Detecta inversões e compensações
        inversoes = self._detect_inversions(history[:30])
        compensacoes = self._detect_compensations(history[:20])
        
        # 4. Normaliza scores usando método da classe base
        scores_normalizados = self.normalize_scores(candidates_scores)
        
        # 5. Ordena candidatos por score normalizado
        sorted_candidates = sorted(
            scores_normalizados.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 6. Prepara listas de retorno
        candidatos = [num for num, _ in sorted_candidates]
        scores = dict(sorted_candidates)
        
        # 6. Metadados completos
        resumo = self._get_summary()
        metadata = {
            "total_numeros": len(history),
            "total_cadeias_aprendidas": resumo['total_cadeias'],
            "cadeias_por_tamanho": resumo['por_tamanho'],
            "inversoes_detectadas": len(inversoes),
            "compensacoes_detectadas": len(compensacoes),
            "top_pares": resumo['top_pares'][:5],
            "parametros": {
                "min_support": self.min_support,
                "decay": self.decay,
                "miss_window": self.miss_window,
                "max_chain_length": self.max_length
            }
        }
        
        if inversoes:
            metadata["inversoes"] = [
                {
                    "par_original": inv['par_original'],
                    "par_invertido": inv['par_invertido'],
                    "distancia": inv['distancia']
                }
                for inv in inversoes[:3]
            ]
        
        if compensacoes:
            metadata["compensacoes"] = [
                {
                    "trio_base": comp['trio_base'],
                    "numero_compensado": comp['numero_compensado'],
                    "tipo": comp['tipo']
                }
                for comp in compensacoes[:3]
            ]
        
        logger.info(
            f"CHAIN analysis: {len(candidatos)} candidatos, "
            f"{resumo['total_cadeias']} cadeias aprendidas"
        )
        
        return PatternResult(
            candidatos=candidatos,
            scores=scores,
            metadata=metadata,
            pattern_name="chain"
        )
    
    def _learn_from_history(self, history: List[int]) -> None:
        """
        Aprende cadeias a partir do histórico completo
        
        Args:
            history: Lista de números (topo = mais recente)
        """
        # Limpa aprendizado anterior
        self.chains.clear()
        self.pair_cache.clear()
        
        # Inverte para processar do mais antigo ao mais recente
        reversed_hist = list(reversed(history))
        
        # Aprende cadeias de diferentes comprimentos
        for chain_len in range(1, self.max_length + 1):
            self._learn_chains_of_length(reversed_hist, chain_len)
        
        # Aprende pares simples para cache rápido
        self._learn_pairs(reversed_hist)
    
    def _learn_chains_of_length(self, history: List[int], length: int) -> None:
        """
        Aprende cadeias de um comprimento específico
        
        Ex: length=2 → [10, 20] → 11
        """
        for i in range(len(history) - length):
            # Pega a sequência
            sequence = tuple(history[i:i + length])
            outcome = history[i + length]
            
            # Calcula peso com decaimento temporal
            position_weight = self.decay ** (len(history) - i - length)
            
            # Procura se já existe esse padrão
            existing = None
            for pattern in self.chains[length][sequence]:
                if pattern.outcome == outcome:
                    existing = pattern
                    break
            
            if existing:
                # Atualiza padrão existente
                existing.count += 1
                existing.last_seen = i
                existing.confidence += position_weight
            else:
                # Cria novo padrão
                new_pattern = ChainPattern(
                    sequence=sequence,
                    outcome=outcome,
                    count=1,
                    last_seen=i,
                    confidence=position_weight
                )
                self.chains[length][sequence].append(new_pattern)
    
    def _learn_pairs(self, history: List[int]) -> None:
        """Aprende pares simples X→Y para acesso rápido"""
        for i in range(len(history) - 1):
            from_num = history[i]
            to_num = history[i + 1]
            self.pair_cache[from_num][to_num] += 1
    
    def _find_candidates(self, recent_history: List[int]) -> Dict[int, float]:
        """
        Encontra candidatos baseado nas cadeias aprendidas
        
        Args:
            recent_history: Histórico recente (topo = mais recente)
            
        Returns:
            Dict {numero: score}
        """
        candidates = defaultdict(float)
        
        # Para cada tamanho de cadeia
        for chain_len in range(1, min(self.max_length + 1, len(recent_history) + 1)):
            # Pega o sufixo atual (invertido para ordem cronológica)
            suffix = tuple(recent_history[:chain_len][::-1])
            
            # Procura padrões que começam com esse sufixo
            if suffix in self.chains[chain_len]:
                patterns = self.chains[chain_len][suffix]
                
                # Filtra por suporte mínimo
                valid_patterns = [p for p in patterns if p.count >= self.min_support]
                
                if valid_patterns:
                    # Ordena por confiança
                    valid_patterns.sort(key=lambda p: p.confidence, reverse=True)
                    
                    # Pondera cada outcome
                    for pattern in valid_patterns[:5]:  # Top 5 padrões (aumentado de 3)
                        # Peso maior e multiplicador aumentado
                        weight = pattern.confidence * (2.0 + 0.5 * chain_len)  # Aumentado!
                        candidates[pattern.outcome] += weight
        
        # FALLBACK: Se poucos candidatos, usa pares mais frequentes
        if len(candidates) < 5:
            ultimo_num = recent_history[0] if recent_history else None
            if ultimo_num and ultimo_num in self.pair_cache:
                for to_num, count in self.pair_cache[ultimo_num].most_common(10):
                    if count >= 1:  # Aceita até ocorrência única
                        # Peso aumentado para competir melhor no ensemble
                        fallback_weight = count * 1.5  # Aumentado de 0.5 para 1.5
                        candidates[to_num] += fallback_weight
        
        # Identifica faltantes
        missing_bonus = self._calculate_missing_bonus(
            recent_history[:self.miss_window],
            dict(candidates)
        )
        
        # Aplica bônus de faltante (aumentado ainda mais)
        for num, bonus in missing_bonus.items():
            if num in candidates:
                candidates[num] *= (1.0 + bonus * 2.0)  # Bônus 2x (era 1.5x)
        
        # Se ainda poucos candidatos, adiciona números com bônus de faltante
        if len(candidates) < 3:
            recent_set = set(recent_history[:self.miss_window])
            # Adiciona números que não aparecem há muito tempo
            for num in range(37):
                if num not in recent_set and num not in candidates:
                    # Peso base pequeno para diversificar
                    candidates[num] = 0.1
        
        return dict(candidates)
    
    def _calculate_missing_bonus(self, recent: List[int], candidates: Dict[int, float]) -> Dict[int, float]:
        """
        Calcula bônus para números "faltantes"
        
        Um número é faltante se:
        1. Tem forte suporte nas cadeias
        2. NÃO apareceu recentemente
        """
        bonus = {}
        recent_set = set(recent)
        
        if not candidates:
            return bonus
        
        max_weight = max(candidates.values()) if candidates else 1.0
        
        # Os top candidatos que não aparecem recentemente ganham bônus
        sorted_candidates = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
        
        for num, weight in sorted_candidates[:15]:  # Aumentado de 10 para 15
            if num not in recent_set:
                # Bônus proporcional ao peso (máx 80%, aumentado de 50%)
                bonus[num] = min(0.8, (weight / max_weight) * 0.8)
        
        return bonus
    
    def _detect_inversions(self, recent: List[int], lookback: int = 20) -> List[Dict]:
        """
        Detecta inversões comportamentais (ex: 33→5 depois 5→33)
        
        Args:
            recent: Histórico recente (topo = mais recente)
            lookback: Quantos números olhar para trás
            
        Returns:
            Lista de inversões detectadas
        """
        inversions = []
        
        if len(recent) < 2:
            return inversions
        
        for i in range(min(len(recent) - 1, lookback)):
            pair = (recent[i], recent[i + 1])
            reversed_pair = (pair[1], pair[0])
            
            # Procura se o par invertido apareceu antes
            for j in range(i + 2, min(len(recent) - 1, lookback)):
                if (recent[j], recent[j + 1]) == reversed_pair:
                    inversions.append({
                        'par_original': pair,
                        'par_invertido': reversed_pair,
                        'distancia': j - i,
                        'tipo': 'inversao_comportamental'
                    })
                    break
        
        return inversions
    
    def _detect_compensations(self, recent: List[int], window: int = 10) -> List[Dict]:
        """
        Detecta compensações (ex: 27-11-36 faltando 13 → depois paga 13)
        
        Procura por "vizinhos faltantes" ou "espelhos faltantes"
        """
        compensations = []
        
        # Para cada trio recente
        for i in range(min(len(recent) - 2, window)):
            trio = recent[i:i + 3]
            
            # Pega todos os vizinhos dos três números
            all_neighbors = set()
            for num in trio:
                all_neighbors.update(get_vizinhos(num))
            
            # Remove os que já apareceram
            all_neighbors -= set(trio)
            
            # Verifica quais vizinhos aparecem logo depois
            for j in range(i + 3, min(i + 10, len(recent))):
                if recent[j] in all_neighbors:
                    compensations.append({
                        'trio_base': trio,
                        'numero_compensado': recent[j],
                        'tipo': 'vizinho_faltante',
                        'distancia': j - i - 2
                    })
        
        return compensations
    
    def _get_summary(self) -> Dict:
        """Retorna resumo do aprendizado atual"""
        total_chains = sum(len(seqs) for seqs in self.chains.values())
        
        summary = {
            'total_cadeias': total_chains,
            'por_tamanho': {},
            'top_pares': []
        }
        
        # Cadeias por tamanho
        for length, seqs in self.chains.items():
            summary['por_tamanho'][length] = len(seqs)
        
        # Top pares mais frequentes
        all_pairs = []
        for from_num, to_counts in self.pair_cache.items():
            for to_num, count in to_counts.items():
                all_pairs.append({'de': from_num, 'para': to_num, 'vezes': count})
        
        all_pairs.sort(key=lambda x: x['vezes'], reverse=True)
        summary['top_pares'] = all_pairs[:10]
        
        return summary


# ===== INSTÂNCIA GLOBAL (para reutilização) =====
_chain_instance: Optional[ChainAnalyzer] = None


def get_chain_analyzer(config: Dict[str, Any] = None) -> ChainAnalyzer:
    """
    Retorna instância singleton do ChainAnalyzer
    Útil para evitar recriar o analisador em cada request
    """
    global _chain_instance
    if _chain_instance is None:
        _chain_instance = ChainAnalyzer(config)
    return _chain_instance