"""
patterns/puxadas.py

Padrão PUXADAS - Identifica números que são puxados após um gatilho
Baseado em análise estatística pré-calculada
"""

import json
import os
from typing import List, Dict
from collections import Counter

import logging


from patterns.base import BasePattern, PatternResult


logger = logging.getLogger(__name__)


class PuxadasPattern(BasePattern):
    """
    Padrão que identifica números "puxados" após um número gatilho
    
    Usa análise pré-calculada (JSON) para determinar quais números
    têm alta probabilidade de aparecer após determinados gatilhos.
    """
    
    def __init__(self, config: Dict = None, json_path: str = "data/analise_puxadas_completa.json"):
        """
        Inicializa o padrão Puxadas
        
        Args:
            config: Configurações do padrão
            json_path: Caminho para o JSON com análise de puxadas
        """
        default_config = {
            "top_n": 18,           # Quantos números puxados considerar
            "peso_decaimento": 0.9, # Decaimento por posição no ranking
            "min_lift": 0.2,       # Lift mínimo para considerar
            "usar_prob": False     # Se True, usa probabilidade; se False, usa lift
        }
        
        if config:
            default_config.update(config)
        
        super().__init__(default_config)
        
        # Carrega dados de puxadas
        self.json_path = json_path
        self.dados_puxadas = self._carregar_dados()
    
    def _carregar_dados(self) -> Dict:
        """Carrega o JSON com análise de puxadas"""
        try:
            # Tenta vários caminhos possíveis
            caminhos_possiveis = [
                self.json_path,
                os.path.join("data", "analise_puxadas_completa.json"),
                os.path.join("..", "data", "analise_puxadas_completa.json"),
                "analise_puxadas_completa.json"
            ]
            
            for caminho in caminhos_possiveis:
                if os.path.exists(caminho):
                    with open(caminho, 'r', encoding='utf-8') as f:
                        dados = json.load(f)
                        logger.info(f"✅ Dados de puxadas carregados de: {caminho}")
                        return dados.get('analise_por_numero', {})
            
            logger.error(f"❌ Arquivo de puxadas não encontrado nos caminhos: {caminhos_possiveis}")
            return {}
        
        except Exception as e:
            logger.error(f"Erro ao carregar dados de puxadas: {e}")
            return {}
    
    def _get_puxados(self, numero_gatilho: int) -> List[Dict]:
        """
        Retorna lista de números puxados pelo gatilho
        
        Args:
            numero_gatilho: Número que serve como gatilho
        
        Returns:
            Lista de dicts com informações dos números puxados
        """
        chave = str(numero_gatilho)
        
        if chave not in self.dados_puxadas:
            return []
        
        analise = self.dados_puxadas[chave]
        top_puxados = analise.get('top_puxados', [])

        print(len(top_puxados), "PUXADOS SEM FILTRAR")

        
        # Filtra por lift mínimo
        min_lift = self.config.get('min_lift', 0.1)
        puxados_filtrados = [
            p for p in top_puxados 
            if p.get('lift', 0) >= min_lift
        ]

        
        # Limita ao top_n
        top_n = self.config.get('top_n', 18)

        
        return top_puxados[:top_n]
    
    def analyze(self, historico: List[int]) -> PatternResult:
        """
        Analisa o histórico e retorna números puxados pelo último número
        
        Args:
            historico: Lista de números (mais recente no índice 0)
        
        Returns:
            PatternResult com scores dos números puxados
        """
        if not historico or len(historico) < 1:
            return PatternResult(
                scores={},
                metadata={'erro': 'Histórico insuficiente'}
            )
        
        if not self.dados_puxadas:
            return PatternResult(
                scores={},
                metadata={'erro': 'Dados de puxadas não carregados'}
            )
        
        # Pega o último número (gatilho)
        numero_gatilho = historico[0]
        
        # Busca os números puxados
        puxados = self._get_puxados(numero_gatilho)

        
        if not puxados:
            return PatternResult(
                scores={},
                metadata={
                    'numero_gatilho': numero_gatilho,
                    'puxados_encontrados': 0,
                    'mensagem': f'Nenhum número puxado significativo encontrado para {numero_gatilho}'
                }
            )
        
        # Calcula scores
        scores = {}
        usar_prob = self.config.get('usar_prob', False)
        peso_decaimento = self.config.get('peso_decaimento', 0.9)
        
        for i, puxado in enumerate(puxados):
            numero = puxado['numero']
            
            # Usa lift ou probabilidade como base
            if usar_prob:
                score_base = puxado.get('prob', 0) / 100.0  # Normaliza probabilidade
            else:
                score_base = puxado.get('lift', 1.0)
            
            # Aplica decaimento por posição (1º lugar vale mais)
            peso_posicao = peso_decaimento ** i
            score_final = score_base * peso_posicao
            
            scores[numero] = score_final
        
        # Normaliza scores (0-1)
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                scores = {num: score / max_score for num, score in scores.items()}
        
        # Metadata
        metadata = {
            'numero_gatilho': numero_gatilho,
            'puxados_encontrados': len(puxados),
            'top_3_puxados': [p['numero'] for p in puxados[:3]],
            'lifts_top_3': [p['lift'] for p in puxados[:3]],
            'modo': 'lift' if not usar_prob else 'probabilidade',
            'config': {
                'top_n': self.config.get('top_n'),
                'min_lift': self.config.get('min_lift'),
                'peso_decaimento': peso_decaimento
            }
        }

        candidatos = [item['numero'] for item in puxados]

        
        return PatternResult(candidatos=candidatos, scores=scores, metadata=metadata, pattern_name='PUXADAS')

    
    def get_info(self) -> Dict:
        """Retorna informações sobre o padrão"""
        return {
            'nome': 'Puxadas',
            'descricao': 'Identifica números que são puxados após um gatilho',
            'dados_carregados': len(self.dados_puxadas) > 0,
            'total_gatilhos': len(self.dados_puxadas),
            'config': self.config
        }