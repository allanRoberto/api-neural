"""
patterns/master.py

Padrão MASTER - Análise de padrões exatos e recorrentes

O MASTER busca sequências que JÁ OCORRERAM no histórico e identifica
quais números vieram em seguida nessas ocorrências anteriores.

Características:
- Trabalha com janelas de 2-5 números consecutivos
- Aplica decaimento temporal (ocorrências recentes valem mais)
- Identifica relações: vizinhos, espelhos, terminais, soma
- Pontua candidatos baseado na força das relações
"""

from typing import List, Dict, Tuple
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
    encontrar_sequencia,
)

logger = logging.getLogger(__name__)


class MasterPattern(BasePattern):
    """
    Padrão MASTER - Busca padrões exatos que se repetem
    
    Exemplo de uso:
        master = MasterPattern(config={
            'janela_min': 2,
            'janela_max': 4,
            'decay_factor': 0.95,
            'min_support': 2
        })
        
        resultado = master.analyze(history)
        print(resultado.get_top_n(6))  # Top 6 candidatos
    """
    
    def __init__(self, config: Dict = None):
        """
        Inicializa o padrão MASTER
        
        Args:
            config: Configurações do padrão
                - janela_min: Tamanho mínimo da janela (default: 2)
                - janela_max: Tamanho máximo da janela (default: 4)
                - decay_factor: Fator de decaimento temporal (default: 0.95)
                - min_support: Mínimo de ocorrências para considerar (default: 2)
        """
        super().__init__(config)
        
        self.janela_min = self.get_config_value('janela_min', 2)
        self.janela_max = self.get_config_value('janela_max', 4)
        self.decay_factor = self.get_config_value('decay_factor', 0.95)
        self.min_support = self.get_config_value('min_support', 2)
    
    def analyze(self, history: List[int]) -> PatternResult:
        """
        Analisa o histórico buscando padrões exatos
        
        Args:
            history: Lista de números (mais recente no índice 0)
        
        Returns:
            PatternResult com candidatos e scores
        """
        logger.info(f"🔍 MASTER: Analisando {len(history)} números")
        
        # Validar histórico
        if not self.validate_history(history, min_size=10):
            logger.warning("⚠️ MASTER: Histórico insuficiente")
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={'error': 'Histórico insuficiente'},
                pattern_name='MASTER'
            )
        
        # Inicializar scores
        scores = defaultdict(float)
        
        # Metadados para debug
        metadata = {
            'janelas_analisadas': 0,
            'padroes_encontrados': 0,
            'relacoes_detectadas': {},
        }
        
        # Analisar diferentes tamanhos de janela
        for janela_size in range(self.janela_min, self.janela_max + 1):
            padroes = self._buscar_padroes_exatos(
                history,
                janela_size,
                scores,
                metadata
            )
        
        # Aplicar relações (vizinhos, espelhos, terminais)
        self._aplicar_relacoes(history, scores, metadata)
        
        # Normalizar scores
        scores_normalizados = self.normalize_scores(dict(scores))
        
        # Ordenar candidatos por score
        candidatos = sorted(
            scores_normalizados.keys(),
            key=lambda n: scores_normalizados[n],
            reverse=True
        )
        
        logger.info(
            f"✅ MASTER: {len(candidatos)} candidatos, "
            f"{metadata['padroes_encontrados']} padrões"
        )
        
        return PatternResult(
            candidatos=candidatos,
            scores=scores_normalizados,
            metadata=metadata,
            pattern_name='MASTER'
        )
    
    def _buscar_padroes_exatos(
        self,
        history: List[int],
        janela_size: int,
        scores: Dict[int, float],
        metadata: Dict
    ) -> int:
        """
        Busca padrões exatos de um tamanho específico de janela
        
        Args:
            history: Histórico completo
            janela_size: Tamanho da janela a buscar
            scores: Dicionário de scores (será atualizado)
            metadata: Metadados (será atualizado)
        
        Returns:
            Quantidade de padrões encontrados
        """
        # Sequência atual (mais recente)
        if len(history) < janela_size:
            return 0
        
        sequencia_atual = history[:janela_size]
        metadata['janelas_analisadas'] += 1
        
        # Buscar essa sequência no resto do histórico
        ocorrencias = encontrar_sequencia(
            history[janela_size:],  # Ignorar a própria sequência
            sequencia_atual
        )
        
        if len(ocorrencias) < self.min_support:
            return 0
        
        # Para cada ocorrência passada, ver o que veio depois
        padroes_encontrados = 0
        
        for idx_ocorrencia in ocorrencias:
            # Índice real no histórico (compensar offset)
            idx_real = idx_ocorrencia + janela_size
            
            # Verificar se há um número depois
            if idx_real + 1 < len(history):
                numero_seguinte = history[idx_real + 1]
                
                # Calcular peso com decaimento temporal
                # Quanto mais antiga a ocorrência, menor o peso
                peso = self._calcular_peso_temporal(idx_real, len(history))
                
                # Adicionar score ao número seguinte
                scores[numero_seguinte] += peso
                padroes_encontrados += 1
        
        if padroes_encontrados > 0:
            metadata['padroes_encontrados'] += padroes_encontrados
            logger.debug(
                f"   Janela {janela_size}: {sequencia_atual} → "
                f"{padroes_encontrados} ocorrências"
            )
        
        return padroes_encontrados
    
    def _calcular_peso_temporal(self, posicao: int, total: int) -> float:
        """
        Calcula peso baseado na posição temporal
        
        Posições mais recentes (menor índice) têm peso maior
        
        Args:
            posicao: Posição no histórico (0 = mais recente)
            total: Tamanho total do histórico
        
        Returns:
            Peso entre 0 e 1
        """
        # Normalizar posição (0 = mais recente, 1 = mais antigo)
        pos_normalizada = posicao / total
        
        # Aplicar decaimento exponencial
        peso = self.decay_factor ** pos_normalizada
        
        return peso
    
    def _aplicar_relacoes(
        self,
        history: List[int],
        scores: Dict[int, float],
        metadata: Dict
    ):
        """
        Aplica bônus baseado em relações entre números
        
        Relações consideradas:
        - Vizinhos na roda
        - Espelhos
        - Família terminal
        - Mesma soma de dígitos
        
        Args:
            history: Histórico completo
            scores: Dicionário de scores (será atualizado)
            metadata: Metadados (será atualizado)
        """
        if len(history) < 1:
            return
        
        numero_mais_recente = history[0]
        relacoes = defaultdict(int)
        
        # 1. VIZINHOS
        vizinhos = get_vizinhos(numero_mais_recente, distancia=2)
        for viz in vizinhos:
            if 0 <= viz <= 36:
                scores[viz] += 0.5
                relacoes['vizinhos'] += 1
        
        # 2. ESPELHO
        espelho = get_espelho(numero_mais_recente)
        if espelho != -1:
            scores[espelho] += 0.8
            relacoes['espelhos'] += 1
        
        # 3. FAMÍLIA TERMINAL
        terminal = get_terminal(numero_mais_recente)
        familia = get_familia_terminal(terminal)
        for num in familia:
            if num != numero_mais_recente:
                scores[num] += 0.3
                relacoes['terminais'] += 1
        
        # 4. MESMA SOMA DE DÍGITOS
        nums_mesma_soma = get_numeros_mesma_soma(numero_mais_recente)
        for num in nums_mesma_soma[:5]:  # Limitar a 5
            scores[num] += 0.2
            relacoes['soma'] += 1
        
        # 5. NÚMEROS DO CONTEXTO RECENTE (últimos 10)
        contexto = history[:10]
        frequencia = Counter(contexto)
        for num, freq in frequencia.most_common(5):
            if num != numero_mais_recente:
                scores[num] += 0.1 * freq
                relacoes['contexto'] += 1
        
        metadata['relacoes_detectadas'] = dict(relacoes)
    
    def get_analise_detalhada(self, history: List[int]) -> Dict:
        """
        Retorna análise detalhada do padrão MASTER
        
        Útil para debugging e visualização
        
        Args:
            history: Lista de números
        
        Returns:
            Dicionário com análise completa
        """
        resultado = self.analyze(history)
        
        return {
            'pattern': 'MASTER',
            'historico_size': len(history),
            'ultimos_10': history[:10],
            'top_candidatos': resultado.get_top_n(10),
            'total_candidatos': len(resultado.candidatos),
            'metadata': resultado.metadata,
            'config': {
                'janela_min': self.janela_min,
                'janela_max': self.janela_max,
                'decay_factor': self.decay_factor,
                'min_support': self.min_support,
            }
        }