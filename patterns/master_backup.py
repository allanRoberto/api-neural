"""
patterns/master_melhorado.py

MASTER MELHORADO - Relações como MULTIPLICADORES ao invés de ADITIVOS

Mudança principal:
- Antes: score_final = padrões + relações (relações dominavam)
- Agora: score_final = padrões × (1 + bônus_relações) (padrões dominam)
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
    Padrão MASTER Melhorado
    
    Mudanças:
    1. min_support padrão = 1 (mais sensível)
    2. Relações são MULTIPLICADORES (não aditivos)
    3. Se 0 padrões, usa fallback com peso reduzido
    """
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        
        self.janela_min = self.get_config_value('janela_min', 2)
        self.janela_max = self.get_config_value('janela_max', 2)  # Mudou de 4 para 2
        self.decay_factor = self.get_config_value('decay_factor', 0.96)
        self.min_support = self.get_config_value('min_support', 1)
        
        # Novos parâmetros
        self.peso_relacoes = self.get_config_value('peso_relacoes', 0.25)
        self.usar_fallback = self.get_config_value('usar_fallback', True)
        self.janelas_recentes = self.get_config_value('janelas_recentes', 10)  # Analisa 5 janelas
    
    def analyze(self, history: List[int]) -> PatternResult:
        """Analisa o histórico buscando padrões exatos"""
        
        logger.info(f"🔍 MASTER MELHORADO: Analisando {len(history)} números")
        
        if not self.validate_history(history, min_size=10):
            logger.warning("⚠️ MASTER: Histórico insuficiente")
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={'error': 'Histórico insuficiente'},
                pattern_name='MASTER_MELHORADO'
            )
        
        # Inicializar scores de PADRÕES
        scores_padroes = defaultdict(float)
        
        metadata = {
            'janelas_analisadas': 0,
            'padroes_encontrados': 0,
            'relacoes_detectadas': {},
            'modo': 'normal'
        }
        
        # 1. BUSCAR PADRÕES EXATOS
        # NOVO: Analisa múltiplas janelas recentes (não só a última)
        
        for janela_size in range(self.janela_min, self.janela_max + 1):
            for offset in range(self.janelas_recentes):
                # Verificar se há dados suficientes
                fim_janela = offset + janela_size
                busca_inicio = fim_janela + janela_size  # Precisa espaço para buscar
                
                if busca_inicio >= len(history):
                    break
                
                self._buscar_padroes_exatos_offset(
                    history,
                    janela_size,
                    offset,
                    scores_padroes,
                    metadata
                )
        
        # 2. APLICAR RELAÇÕES COMO MULTIPLICADORES
        if metadata['padroes_encontrados'] > 0:
            # Modo normal: padrões × (1 + bônus_relações)
            scores_finais = self._aplicar_relacoes_multiplicador(
                history,
                scores_padroes,
                metadata
            )
        else:
            # Modo fallback: usar relações com peso reduzido
            if self.usar_fallback:
                logger.warning("⚠️ 0 padrões encontrados, usando fallback")
                scores_finais = self._fallback_relacoes(history, metadata)
                metadata['modo'] = 'fallback'
            else:
                scores_finais = {}
        
        # 3. NORMALIZAR
        scores_normalizados = self.normalize_scores(dict(scores_finais))
        
        # 4. ORDENAR
        candidatos = sorted(
            scores_normalizados.keys(),
            key=lambda n: scores_normalizados[n],
            reverse=True
        )
        
        logger.info(
            f"✅ MASTER MELHORADO: {len(candidatos)} candidatos, "
            f"{metadata['padroes_encontrados']} padrões, "
            f"modo={metadata['modo']}"
        )
        
        return PatternResult(
            candidatos=candidatos,
            scores=scores_normalizados,
            metadata=metadata,
            pattern_name='MASTER_MELHORADO'
        )
    
    def _buscar_padroes_exatos_offset(
        self,
        history: List[int],
        janela_size: int,
        offset: int,
        scores: Dict[int, float],
        metadata: Dict
    ) -> int:
        """
        Busca padrões exatos com offset (analisa não só os últimos números)
        
        Args:
            history: Histórico completo
            janela_size: Tamanho da janela a buscar
            offset: Deslocamento (0 = últimos números, 1 = penúltimos, etc)
            scores: Dicionário de scores (será atualizado)
            metadata: Metadados (será atualizado)
        
        Returns:
            Quantidade de padrões encontrados
        """
        inicio = offset
        fim = offset + janela_size
        
        if fim > len(history):
            return 0
        
        sequencia_atual = history[inicio:fim]
        metadata['janelas_analisadas'] += 1
        
        # Buscar essa sequência no resto do histórico
        # Importante: evitar buscar na própria janela (overlap mínimo)
        # Reduzido de "fim + janela_size" para "fim + 1" (menos zona morta)
        busca_inicio = fim + 1  # Apenas 1 número de separação
        
        if busca_inicio >= len(history):
            return 0
        
        ocorrencias = encontrar_sequencia(
            history[busca_inicio:],
            sequencia_atual
        )
        
        if len(ocorrencias) < self.min_support:
            return 0
        
        padroes_encontrados = 0
        
        for idx_ocorrencia in ocorrencias:
            idx_real = idx_ocorrencia + busca_inicio
            
            if idx_real + 1 < len(history):
                numero_seguinte = history[idx_real + 1]
                
                # Peso temporal + peso de proximidade
                peso_temporal = self._calcular_peso_temporal(idx_real, len(history))
                peso_proximidade = 1.0 / (offset + 1)  # offset 0 = peso 1.0, offset 1 = peso 0.5
                
                peso_final = peso_temporal * peso_proximidade
                
                scores[numero_seguinte] += peso_final
                padroes_encontrados += 1
        
        if padroes_encontrados > 0:
            metadata['padroes_encontrados'] += padroes_encontrados
            if offset == 0:  # Log só para a janela principal
                logger.debug(
                    f"   Janela {janela_size} (offset {offset}): {sequencia_atual} → "
                    f"{padroes_encontrados} ocorrências"
                )
        
        return padroes_encontrados
    
    def _buscar_padroes_exatos(
        self,
        history: List[int],
        janela_size: int,
        scores: Dict[int, float],
        metadata: Dict
    ) -> int:
        """Busca padrões exatos (IGUAL AO ORIGINAL)"""
        
        if len(history) < janela_size:
            return 0
        
        sequencia_atual = history[:janela_size]
        metadata['janelas_analisadas'] += 1
        
        ocorrencias = encontrar_sequencia(
            history[janela_size:],
            sequencia_atual
        )
        
        if len(ocorrencias) < self.min_support:
            return 0
        
        padroes_encontrados = 0
        
        for idx_ocorrencia in ocorrencias:
            idx_real = idx_ocorrencia + janela_size
            
            if idx_real + 1 < len(history):
                numero_seguinte = history[idx_real + 1]
                peso = self._calcular_peso_temporal(idx_real, len(history))
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
        """Calcula peso baseado na posição temporal"""
        pos_normalizada = posicao / total
        peso = self.decay_factor ** pos_normalizada
        return peso
    
    def _aplicar_relacoes_multiplicador(
        self,
        history: List[int],
        scores_padroes: Dict[int, float],
        metadata: Dict
    ) -> Dict[int, float]:
        """
        Aplica relações como MULTIPLICADORES
        
        Fórmula: score_final = score_padrão × (1 + bônus_relação)
        """
        if len(history) < 1:
            return scores_padroes
        
        numero_mais_recente = history[0]
        scores_finais = defaultdict(float)
        bonus_relacoes = defaultdict(float)
        relacoes = defaultdict(int)
        
        # Calcular bônus por relação
        # 1. VIZINHOS (20% bônus)
        vizinhos = get_vizinhos(numero_mais_recente, distancia=2)
        for viz in vizinhos:
            if 0 <= viz <= 36:
                bonus_relacoes[viz] += 0.20
                relacoes['vizinhos'] += 1
        
        # 2. ESPELHO (30% bônus)
        espelho = get_espelho(numero_mais_recente)
        if espelho != -1:
            bonus_relacoes[espelho] += 0.30
            relacoes['espelhos'] += 1
        
        # 3. FAMÍLIA TERMINAL (15% bônus)
        terminal = get_terminal(numero_mais_recente)
        familia = get_familia_terminal(terminal)
        for num in familia:
            if num != numero_mais_recente:
                bonus_relacoes[num] += 0.15
                relacoes['terminais'] += 1
        
        # 4. MESMA SOMA (10% bônus)
        nums_mesma_soma = get_numeros_mesma_soma(numero_mais_recente)
        for num in nums_mesma_soma[:5]:
            bonus_relacoes[num] += 0.10
            relacoes['soma'] += 1
        
        # 5. CONTEXTO RECENTE (5% bônus por ocorrência)
        contexto = history[:10]
        frequencia = Counter(contexto)
        for num, freq in frequencia.most_common(5):
            if num != numero_mais_recente:
                bonus_relacoes[num] += 0.05 * freq
                relacoes['contexto'] += 1
        
        # Limitar bônus máximo
        max_bonus = self.peso_relacoes  # 30% por padrão
        for num in bonus_relacoes:
            bonus_relacoes[num] = min(bonus_relacoes[num], max_bonus)
        
        # Aplicar multiplicadores
        for num, score_base in scores_padroes.items():
            bonus = bonus_relacoes.get(num, 0)
            scores_finais[num] = score_base * (1 + bonus)
        
        # Números que têm bônus mas não têm padrão: score mínimo
        for num, bonus in bonus_relacoes.items():
            if num not in scores_finais and bonus > 0:
                scores_finais[num] = 0.1 * (1 + bonus)
        
        metadata['relacoes_detectadas'] = dict(relacoes)
        
        return dict(scores_finais)
    
    def _fallback_relacoes(
        self,
        history: List[int],
        metadata: Dict
    ) -> Dict[int, float]:
        """
        Fallback quando 0 padrões são encontrados
        
        Usa apenas relações, mas com pesos REDUZIDOS
        """
        if len(history) < 1:
            return {}
        
        numero_mais_recente = history[0]
        scores = defaultdict(float)
        relacoes = defaultdict(int)
        
        # Pesos REDUZIDOS (50% do normal)
        peso_fallback = 0.5
        
        # VIZINHOS
        vizinhos = get_vizinhos(numero_mais_recente, distancia=2)
        for viz in vizinhos:
            if 0 <= viz <= 36:
                scores[viz] += 0.5 * peso_fallback
                relacoes['vizinhos'] += 1
        
        # ESPELHO
        espelho = get_espelho(numero_mais_recente)
        if espelho != -1:
            scores[espelho] += 0.8 * peso_fallback
            relacoes['espelhos'] += 1
        
        # FAMÍLIA TERMINAL
        terminal = get_terminal(numero_mais_recente)
        familia = get_familia_terminal(terminal)
        for num in familia:
            if num != numero_mais_recente:
                scores[num] += 0.3 * peso_fallback
                relacoes['terminais'] += 1
        
        # CONTEXTO RECENTE (mais importante no fallback)
        contexto = history[:15]
        frequencia = Counter(contexto)
        for num, freq in frequencia.most_common(10):
            if num != numero_mais_recente:
                scores[num] += 0.2 * freq * peso_fallback
                relacoes['contexto'] += 1
        
        metadata['relacoes_detectadas'] = dict(relacoes)
        
        return dict(scores)
    
    def get_analise_detalhada(self, history: List[int]) -> Dict:
        """Retorna análise detalhada"""
        resultado = self.analyze(history)
        
        return {
            'pattern': 'MASTER_MELHORADO',
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
                'peso_relacoes': self.peso_relacoes,
                'janelas_recentes': self.janelas_recentes,
            }
        }