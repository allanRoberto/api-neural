"""
patterns/estelar.py

Padrão ESTELAR - Análise de equivalências subjetivas e comportamentais

O ESTELAR reconhece quando a mesa REPETE COMPORTAMENTOS, mesmo que
com números diferentes, através de EQUIVALÊNCIAS LÓGICAS.

Exemplo:
  Passado: [9, 22, 31]
  Agora:   [19, 31, 22]
  
  Reconhece: 19 é terminal de 9, e 22/31 trocaram de ordem
  → Mesmo comportamento, números equivalentes!
"""

from typing import List, Dict, Tuple, Set
from collections import defaultdict, Counter
import logging

from patterns.base import BasePattern, PatternResult
from utils.helpers import (
    get_vizinhos,
    get_espelho,
    get_terminal,
    get_familia_terminal,
    get_soma_digitos,
    get_numeros_mesma_soma,
    sao_vizinhos,
)

logger = logging.getLogger(__name__)


class EstelarPattern(BasePattern):
    """
    Padrão ESTELAR - Reconhece padrões equivalentes e subjetivos
    
    Características:
    - Trabalha com estruturas de 2-4 números
    - Aceita equivalências: terminais, vizinhos, espelhos, soma
    - Identifica padrões que se repetem de forma "intuitiva"
    - Pondera por força da equivalência
    """
    
    # Espelhos fixos (definidos no documento)
    ESPELHOS = {
        1: 10, 10: 1,
        2: 20, 20: 2,
        3: 30, 30: 3,
        6: 9, 9: 6,
        16: 19, 19: 16,
        26: 29, 29: 26,
        13: 31, 31: 13,
        12: 21, 21: 12,
        32: 23, 23: 32,
    }
    
    def __init__(self, config: Dict = None):
        """
        Inicializa o padrão ESTELAR
        
        Args:
            config: Configurações
                - estrutura_min: Tamanho mínimo da estrutura (default: 2)
                - estrutura_max: Tamanho máximo da estrutura (default: 4)
                - min_support: Mínimo de ocorrências (default: 2)
                - peso_equivalencias: Pesos por tipo (dict)
        """
        super().__init__(config)
        
        self.estrutura_min = self.get_config_value('estrutura_min', 2)
        self.estrutura_max = self.get_config_value('estrutura_max', 3)  # Reduzido de 4 para 3
        self.min_support = self.get_config_value('min_support', 2)      # Aumentado de 1 para 2
        
        # Pesos das equivalências
        self.peso_equivalencias = self.get_config_value('peso_equivalencias', {
            'exato': 1.0,
            'espelho': 0.9,
            'terminal': 0.8,
            'vizinho': 0.7,
            'soma': 0.6,
            'dobro_metade': 0.5,
            'mesma_duzia': 0.4,
            'mesma_coluna': 0.4,
        })
        
        # Bonus para alternâncias
        self.bonus_alternancia = self.get_config_value('bonus_alternancia', 1.3)
    
    def analyze(self, history: List[int]) -> PatternResult:
        """
        Analisa o histórico buscando padrões equivalentes
        
        Args:
            history: Lista de números (mais recente no índice 0)
        
        Returns:
            PatternResult com candidatos e scores
        """
        logger.info(f"🌟 ESTELAR: Analisando {len(history)} números")
        
        if not self.validate_history(history, min_size=20):
            logger.warning("⚠️ ESTELAR: Histórico insuficiente")
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={'error': 'Histórico insuficiente'},
                pattern_name='ESTELAR'
            )
        
        # Inicializar scores
        scores = defaultdict(float)
        
        metadata = {
            'estruturas_analisadas': 0,
            'padroes_equivalentes': 0,
            'tipos_equivalencia': defaultdict(int),
        }
        
        # Buscar padrões equivalentes de diferentes tamanhos
        for tam in range(self.estrutura_min, self.estrutura_max + 1):
            self._buscar_estruturas_equivalentes(
                history,
                tam,
                scores,
                metadata
            )
        
        # Normalizar scores
        scores_normalizados = self.normalize_scores(dict(scores))
        
        # Ordenar candidatos
        candidatos = sorted(
            scores_normalizados.keys(),
            key=lambda n: scores_normalizados[n],
            reverse=True
        )
        
        logger.info(
            f"✅ ESTELAR: {len(candidatos)} candidatos, "
            f"{metadata['padroes_equivalentes']} padrões equivalentes"
        )
        
        return PatternResult(
            candidatos=candidatos,
            scores=scores_normalizados,
            metadata=dict(metadata),
            pattern_name='ESTELAR'
        )
    
    def _buscar_estruturas_equivalentes(
        self,
        history: List[int],
        tamanho: int,
        scores: Dict[int, float],
        metadata: Dict
    ):
        """
        Busca estruturas equivalentes de um tamanho específico
        
        Args:
            history: Histórico completo
            tamanho: Tamanho da estrutura
            scores: Dicionário de scores (será atualizado)
            metadata: Metadados (será atualizado)
        """
        if len(history) < tamanho + 1:
            return
        
        # Estrutura atual (mais recente)
        estrutura_atual = history[:tamanho]
        metadata['estruturas_analisadas'] += 1
        
        # Buscar estruturas equivalentes no passado
        for i in range(tamanho, len(history) - tamanho):
            estrutura_passada = history[i:i+tamanho]
            
            # Verificar se são equivalentes
            tipo_equiv, forca = self._sao_equivalentes(
                estrutura_atual,
                estrutura_passada
            )
            
            if tipo_equiv is None:
                continue
            
            # Estruturas equivalentes encontradas!
            metadata['padroes_equivalentes'] += 1
            metadata['tipos_equivalencia'][tipo_equiv] += 1
            
            # Ver o que veio depois da estrutura passada
            if i + tamanho < len(history):
                numero_seguinte = history[i + tamanho]
                
                # Calcular peso
                peso = forca * self._calcular_peso_temporal(i, len(history))
                
                # Aplicar bônus se for alternância
                if self._detectar_alternancia(estrutura_passada):
                    peso *= self.bonus_alternancia
                
                scores[numero_seguinte] += peso
                
                # Adicionar equivalentes do número seguinte
                equivalentes = self._gerar_equivalentes(numero_seguinte)
                for equiv, peso_equiv in equivalentes:
                    scores[equiv] += peso * peso_equiv
    
    def _sao_equivalentes(
        self,
        seq1: List[int],
        seq2: List[int]
    ) -> Tuple[str, float]:
        """
        Verifica se duas sequências são equivalentes
        
        Args:
            seq1: Primeira sequência
            seq2: Segunda sequência
        
        Returns:
            (tipo_equivalencia, força) ou (None, 0) se não equivalentes
        """
        if len(seq1) != len(seq2):
            return None, 0
        
        # 1. EXATO (mesmos números)
        if seq1 == seq2:
            return 'exato', self.peso_equivalencias['exato']
        
        # 2. ESPELHOS (todos são espelhos)
        if all(self._sao_espelhos(a, b) for a, b in zip(seq1, seq2)):
            return 'espelho', self.peso_equivalencias['espelho']
        
        # 3. TERMINAIS (mesma família terminal)
        if all(get_terminal(a) == get_terminal(b) for a, b in zip(seq1, seq2)):
            return 'terminal', self.peso_equivalencias['terminal']
        
        # 4. VIZINHOS (todos são vizinhos)
        if all(sao_vizinhos(a, b) for a, b in zip(seq1, seq2)):
            return 'vizinho', self.peso_equivalencias['vizinho']
        
        # 5. SOMA DE DÍGITOS (mesma soma)
        if all(get_soma_digitos(a) == get_soma_digitos(b) for a, b in zip(seq1, seq2)):
            return 'soma', self.peso_equivalencias['soma']
        
        # 6. MESMA ESTRUTURA (padrão ABA, ABAB, etc)
        if self._mesma_estrutura(seq1, seq2):
            return 'estrutura', 0.6
        
        # 7. INVERSÃO (seq2 é seq1 invertida)
        if seq1 == list(reversed(seq2)):
            return 'inversao', 0.7
        
        return None, 0
    
    def _sao_espelhos(self, a: int, b: int) -> bool:
        """Verifica se dois números são espelhos"""
        return self.ESPELHOS.get(a) == b
    
    def _mesma_estrutura(self, seq1: List[int], seq2: List[int]) -> bool:
        """
        Verifica se duas sequências têm a mesma estrutura
        
        Exemplo:
          [9, 22, 31] e [19, 31, 22]
          Estrutura: A-B-C e A'-C-B (similar)
        """
        if len(seq1) != len(seq2):
            return False
        
        # Criar padrão de repetições
        def criar_padrao(seq):
            padrao = []
            mapa = {}
            proximo_id = 0
            
            for num in seq:
                if num not in mapa:
                    mapa[num] = proximo_id
                    proximo_id += 1
                padrao.append(mapa[num])
            
            return tuple(padrao)
        
        padrao1 = criar_padrao(seq1)
        padrao2 = criar_padrao(seq2)
        
        # Padrões idênticos
        if padrao1 == padrao2:
            return True
        
        # Padrões com mesma quantidade de repetições
        count1 = Counter(padrao1)
        count2 = Counter(padrao2)
        
        return sorted(count1.values()) == sorted(count2.values())
    
    def _detectar_alternancia(self, seq: List[int]) -> bool:
        """
        Detecta se há alternância na sequência
        
        Alternância: mudança de terminal, setor, cor, etc
        """
        if len(seq) < 2:
            return False
        
        # Alternância de terminais
        terminais = [get_terminal(n) for n in seq]
        if len(set(terminais)) == len(terminais):  # Todos diferentes
            return True
        
        # Alternância de paridade
        paridades = [n % 2 for n in seq]
        if all(paridades[i] != paridades[i+1] for i in range(len(paridades)-1)):
            return True
        
        return False
    
    def _gerar_equivalentes(self, numero: int) -> List[Tuple[int, float]]:
        """
        Gera números equivalentes a um número dado
        
        Args:
            numero: Número base
        
        Returns:
            Lista de (numero_equivalente, peso)
        """
        equivalentes = []
        
        # Espelho
        espelho = self.ESPELHOS.get(numero)
        if espelho is not None and espelho != numero:
            equivalentes.append((espelho, 0.8))
        
        # Família terminal
        terminal = get_terminal(numero)
        familia = get_familia_terminal(terminal)
        for f in familia:
            if f != numero and 0 <= f <= 36:
                equivalentes.append((f, 0.6))
        
        # Vizinhos
        vizinhos = get_vizinhos(numero, distancia=1)
        for v in vizinhos:
            if 0 <= v <= 36:
                equivalentes.append((v, 0.5))
        
        # Mesma soma
        nums_soma = get_numeros_mesma_soma(numero)
        for n in nums_soma[:3]:  # Limitar a 3
            equivalentes.append((n, 0.4))
        
        return equivalentes
    
    def _calcular_peso_temporal(self, posicao: int, total: int) -> float:
        """
        Calcula peso baseado na posição temporal
        
        Args:
            posicao: Posição no histórico (0 = mais recente)
            total: Tamanho total do histórico
        
        Returns:
            Peso entre 0 e 1
        """
        # Decaimento suave
        decay = 0.95
        pos_normalizada = posicao / total
        return decay ** pos_normalizada
    
    def get_analise_detalhada(self, history: List[int]) -> Dict:
        """Retorna análise detalhada do ESTELAR"""
        resultado = self.analyze(history)
        
        return {
            'pattern': 'ESTELAR',
            'historico_size': len(history),
            'ultimos_10': history[:10],
            'top_candidatos': resultado.get_top_n(10),
            'total_candidatos': len(resultado.candidatos),
            'metadata': resultado.metadata,
            'config': {
                'estrutura_min': self.estrutura_min,
                'estrutura_max': self.estrutura_max,
                'min_support': self.min_support,
                'peso_equivalencias': self.peso_equivalencias,
            }
        }