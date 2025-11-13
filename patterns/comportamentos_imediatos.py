"""
patterns/comportamentos_imediatos.py

Análise de comportamentos imediatos nos últimos 10 números
Detecta padrões quentes que precisam confirmação imediata
"""

from typing import List, Dict, Set, Tuple
from collections import defaultdict, Counter
import logging

from utils.constants import ESPELHOS, VIZINHOS
from utils.helpers import get_vizinhos, get_terminal
from patterns.base import PatternResult

logger = logging.getLogger(__name__)


class ComportamentosImediatos:
    """
    Análise rápida dos últimos 10 números
    Detecta padrões quentes com alta probabilidade de continuação
    """
    
    def __init__(self):
        self.janela_analise = 10
        self.cavalos = [
            [2, 5, 8],
            [3, 6, 9], 
            [1, 4, 7]
        ]
        
    def analyze(self, historico: List[int]) -> PatternResult:
        """
        Analisa comportamentos imediatos
        
        Args:
            historico: Lista de números (mais recente primeiro)
            
        Returns:
            PatternResult com scores e metadados
        """
        if len(historico) < self.janela_analise:
            logger.warning(f"Histórico insuficiente: {len(historico)} < {self.janela_analise}")
            return PatternResult()
        
        ultimos_10 = historico[:self.janela_analise]
        scores_totais = defaultdict(float)
        metadata = {
            'janela_analisada': self.janela_analise,
            'ultimos_numeros': ultimos_10,
            'comportamentos_detectados': []
        }
        
        # 1. Detectar alternâncias triplas
        alt_scores, alt_meta = self._detectar_alternancia_tripla(ultimos_10, historico)
        for num, score in alt_scores.items():
            scores_totais[num] += score * 1.5  # Peso maior para alternâncias
        metadata['alternancia_tripla_detectada'] = alt_meta.get('detectada', False)
        if alt_meta.get('detectada'):
            metadata['comportamentos_detectados'].append('alternancia_tripla')
            metadata['alternancia_detalhe'] = alt_meta
        
        # 2. Detectar repetições duplas (vizinhos/espelhos)
        rep_scores, rep_meta = self._detectar_repeticoes_duplas(ultimos_10)
        for num, score in rep_scores.items():
            scores_totais[num] += score * 1.2
        metadata['repeticoes_duplas'] = rep_meta.get('count', 0)
        if rep_meta.get('count', 0) > 0:
            metadata['comportamentos_detectados'].append('repeticoes_duplas')
            metadata['repeticoes_detalhe'] = rep_meta
        
        # 3. Detectar cavalos incompletos
        cav_scores, cav_meta = self._detectar_cavalos_incompletos(ultimos_10)
        for num, score in cav_scores.items():
            scores_totais[num] += score * 1.3
        metadata['cavalos_incompletos'] = cav_meta.get('incompletos', [])
        if cav_meta.get('incompletos'):
            metadata['comportamentos_detectados'].append('cavalos_incompletos')
            metadata['cavalos_detalhe'] = cav_meta
        
        # 4. Detectar substituições comportamentais
        sub_scores, sub_meta = self._detectar_substituicoes(ultimos_10, historico)
        for num, score in sub_scores.items():
            scores_totais[num] += score
        metadata['substituicoes_detectadas'] = sub_meta.get('substituicoes', [])
        if sub_meta.get('substituicoes'):
            metadata['comportamentos_detectados'].append('substituicoes')
            metadata['substituicoes_detalhe'] = sub_meta
        
        # 5. Detectar crescentes/decrescentes
        cresc_scores, cresc_meta = self._detectar_crescentes(ultimos_10)
        for num, score in cresc_scores.items():
            scores_totais[num] += score * 1.1
        metadata['crescentes_detectadas'] = cresc_meta.get('crescentes', [])
        if cresc_meta.get('crescentes'):
            metadata['comportamentos_detectados'].append('crescentes')
            metadata['crescentes_detalhe'] = cresc_meta
            
        # 6. Detectar retornos duplos
        ret_scores, ret_meta = self._detectar_retornos_duplos(ultimos_10)
        for num, score in ret_scores.items():
            scores_totais[num] += score * 1.2
        metadata['retornos_duplos'] = ret_meta.get('count', 0)
        if ret_meta.get('count', 0) > 0:
            metadata['comportamentos_detectados'].append('retornos_duplos')
            metadata['retornos_detalhe'] = ret_meta
        
        # Calcula nível de confiança
        metadata['nivel_confianca'] = self._calcular_confianca(metadata)
        
        return PatternResult(candidatos=list(scores_totais.keys()), scores=dict(scores_totais), metadata=metadata, pattern_name='comportamentos_imediatos')
    
    def _detectar_alternancia_tripla(
        self, 
        ultimos_10: List[int],
        historico_completo: List[int]
    ) -> Tuple[Dict[int, float], Dict]:
        """
        Detecta alternâncias triplas de terminais
        
        Exemplo: Terminal 0 alternou 3x (20 > X > 20 > X > 10)
        """
        scores = defaultdict(float)
        metadata = {'detectada': False, 'terminais': {}, 'proximos_esperados': []}
        
        # Analisa terminais
        terminais = [get_terminal(n) for n in ultimos_10]
        
        # Conta alternâncias por terminal
        for terminal in range(10):
            posicoes = [i for i, t in enumerate(terminais) if t == terminal]
            
            if len(posicoes) >= 3:
                # Verifica se há alternância (posições não consecutivas)
                alternancia = True
                for i in range(len(posicoes) - 1):
                    if posicoes[i+1] - posicoes[i] == 1:  # Consecutivos
                        alternancia = False
                        break
                
                if alternancia:
                    metadata['detectada'] = True
                    metadata['terminais'][terminal] = {
                        'count': len(posicoes),
                        'posicoes': posicoes,
                        'alternancia': True
                    }
                    
                    # Sugere próximo terminal baseado no padrão
                    if posicoes[0] == 0:  # Se último foi esse terminal
                        # Sugere outro terminal que estava alternando
                        for t in range(10):
                            if t != terminal and terminais.count(t) >= 2:
                                # Adiciona números desse terminal
                                for num in range(37):
                                    if get_terminal(num) == t:
                                        scores[num] += 0.8
                    else:
                        # Sugere retorno deste terminal
                        for num in range(37):
                            if get_terminal(num) == terminal:
                                scores[num] += 1.0
                                metadata['proximos_esperados'].append(num)
        
        # Confirma com vizinhos
        if metadata['detectada'] and len(ultimos_10) > 1:
            ultimo = ultimos_10[0]
            penultimo = ultimos_10[1]
            
            # Se último é vizinho do penúltimo, reforça alternância
            if ultimo in get_vizinhos(penultimo, distancia=1):
                for num in metadata['proximos_esperados']:
                    scores[num] *= 1.3
                metadata['confirmacao_vizinho'] = True
        
        return dict(scores), metadata
    
    def _detectar_repeticoes_duplas(self, ultimos_10: List[int]) -> Tuple[Dict[int, float], Dict]:
        """
        Detecta repetições duplas (vizinhos/espelhos)
        
        Exemplo: 20 > 1 (vizinhos), 1 > 10 (espelho)
        """
        scores = defaultdict(float)
        metadata = {'count': 0, 'tipos': [], 'pares': []}
        
        for i in range(len(ultimos_10) - 1):
            atual = ultimos_10[i]
            proximo = ultimos_10[i + 1]
            
            # Verifica vizinhos
            if proximo in get_vizinhos(atual, distancia=1):
                metadata['count'] += 1
                metadata['tipos'].append('vizinho')
                metadata['pares'].append((atual, proximo))
                
                # Sugere continuação de vizinhos
                for viz in get_vizinhos(atual, distancia=1):
                    if viz != proximo:
                        scores[viz] += 0.7
                
            # Verifica espelhos
            if atual in ESPELHOS and ESPELHOS[atual] == proximo:
                metadata['count'] += 1
                metadata['tipos'].append('espelho')
                metadata['pares'].append((atual, proximo))
                
                # Sugere outros espelhos
                for num in ultimos_10[:3]:
                    if num in ESPELHOS:
                        scores[ESPELHOS[num]] += 0.8
        
        # Se detectou 2+ repetições, é padrão forte
        if metadata['count'] >= 2:
            metadata['padrao_forte'] = True
            # Reforça scores
            for num in scores:
                scores[num] *= 1.5
        
        return dict(scores), metadata
    
    def _detectar_cavalos_incompletos(self, ultimos_10: List[int]) -> Tuple[Dict[int, float], Dict]:
        """
        Detecta cavalos incompletos (2 de 3 presentes)
        
        Cavalos: {2,5,8}, {3,6,9}, {1,4,7}
        """
        scores = defaultdict(float)
        metadata = {'incompletos': [], 'faltantes': []}
        
        # Extrai terminais dos últimos números
        terminais_presentes = [get_terminal(n) for n in ultimos_10[:6]]
        
        for cavalo in self.cavalos:
            # Conta quantos do cavalo apareceram
            presentes = []
            for terminal in cavalo:
                count = terminais_presentes.count(terminal)
                if count > 0:
                    presentes.append(terminal)
            
            # Se tem 2 de 3, marca como incompleto
            if len(set(presentes)) == 2:
                faltante = [t for t in cavalo if t not in presentes][0]
                metadata['incompletos'].append({
                    'cavalo': cavalo,
                    'presentes': presentes,
                    'faltante': faltante
                })
                
                # Adiciona todos os números do terminal faltante
                for num in range(37):
                    if get_terminal(num) == faltante:
                        scores[num] += 1.2
                        metadata['faltantes'].append(num)
                
                # Verifica separação de 2 rodadas (comportamento especial)
                if len(presentes) == 2:
                    pos1 = terminais_presentes.index(presentes[0])
                    pos2 = terminais_presentes.index(presentes[1])
                    
                    if abs(pos2 - pos1) == 2:  # Separados por 2 rodadas
                        metadata['separacao_2_rodadas'] = True
                        # Aumenta score do faltante
                        for num in range(37):
                            if get_terminal(num) == faltante:
                                scores[num] *= 1.5
        
        # Confirma com vizinhos
        if metadata['faltantes'] and len(ultimos_10) > 1:
            ultimo = ultimos_10[0]
            for faltante in metadata['faltantes']:
                if ultimo in get_vizinhos(faltante, distancia=1):
                    scores[faltante] *= 1.3
                    metadata['confirmacao_vizinho'] = True
        
        return dict(scores), metadata
    
    def _detectar_substituicoes(
        self, 
        ultimos_10: List[int],
        historico_completo: List[int]
    ) -> Tuple[Dict[int, float], Dict]:
        """
        Detecta substituições comportamentais
        
        Exemplo: 6 substitui 27 (vizinhos), 36 substitui 6 (terminal)
        """
        scores = defaultdict(float)
        metadata = {'substituicoes': [], 'tipos': []}
        
        if len(ultimos_10) < 4:
            return dict(scores), metadata
        
        # Analisa padrão de 3 números
        for i in range(len(ultimos_10) - 3):
            seq = ultimos_10[i:i+3]
            
            # Busca sequência similar no histórico
            for j in range(10, min(len(historico_completo) - 3, 50)):
                seq_hist = historico_completo[j:j+3]
                
                # Verifica se é substituição (2 iguais, 1 diferente)
                iguais = sum(1 for k in range(3) if seq[k] == seq_hist[k])
                
                if iguais == 2:
                    # Encontrou substituição
                    for k in range(3):
                        if seq[k] != seq_hist[k]:
                            original = seq_hist[k]
                            substituto = seq[k]
                            
                            # Identifica tipo de substituição
                            tipo = self._identificar_tipo_substituicao(original, substituto)
                            
                            if tipo:
                                metadata['substituicoes'].append({
                                    'original': original,
                                    'substituto': substituto,
                                    'tipo': tipo,
                                    'posicao': i + k
                                })
                                metadata['tipos'].append(tipo)
                                
                                # Sugere continuação baseada no tipo
                                if tipo == 'vizinho':
                                    # Sugere outros vizinhos
                                    for viz in get_vizinhos(substituto, distancia=1):
                                        scores[viz] += 0.8
                                        
                                elif tipo == 'espelho':
                                    # Sugere espelho do próximo
                                    if j+3 < len(historico_completo):
                                        prox_hist = historico_completo[j+3]
                                        if prox_hist in ESPELHOS:
                                            scores[ESPELHOS[prox_hist]] += 1.0
                                            
                                elif tipo == 'terminal':
                                    # Sugere mesmo terminal
                                    term = get_terminal(substituto)
                                    for num in range(37):
                                        if get_terminal(num) == term and num != substituto:
                                            scores[num] += 0.6
        
        return dict(scores), metadata
    
    def _identificar_tipo_substituicao(self, original: int, substituto: int) -> str:
        """Identifica o tipo de substituição entre dois números"""
        
        # Vizinho?
        if substituto in get_vizinhos(original, distancia=1):
            return 'vizinho'
        
        # Espelho?
        if original in ESPELHOS and ESPELHOS[original] == substituto:
            return 'espelho'
        
        # Mesmo terminal?
        if get_terminal(original) == get_terminal(substituto):
            return 'terminal'
        
        # Dobro/Metade?
        if substituto == original * 2 or original == substituto * 2:
            return 'dobro'
        
        # Soma de dígitos igual?
        soma_orig = sum(int(d) for d in str(original))
        soma_sub = sum(int(d) for d in str(substituto))
        if soma_orig == soma_sub:
            return 'soma'
        
        return None
    
    def _detectar_crescentes(self, ultimos_10: List[int]) -> Tuple[Dict[int, float], Dict]:
        """
        Detecta sequências crescentes/decrescentes
        
        Exemplo: 6 > 12 > 24 (dobro crescente)
        Exemplo: 27 > 28 > 29 (crescente simples)
        """
        scores = defaultdict(float)
        metadata = {'crescentes': [], 'tipos': []}
        
        # Busca crescentes simples (consecutivos)
        for i in range(len(ultimos_10) - 2):
            a, b, c = ultimos_10[i+2], ultimos_10[i+1], ultimos_10[i]
            
            # Crescente simples
            if b == a + 1 and c == b + 1:
                proximo = c + 1
                if 0 <= proximo <= 36:
                    scores[proximo] += 1.2
                    metadata['crescentes'].append({
                        'sequencia': [a, b, c],
                        'tipo': 'simples',
                        'proximo': proximo
                    })
                    metadata['tipos'].append('simples')
            
            # Decrescente simples
            elif b == a - 1 and c == b - 1:
                proximo = c - 1
                if 0 <= proximo <= 36:
                    scores[proximo] += 1.2
                    metadata['crescentes'].append({
                        'sequencia': [a, b, c],
                        'tipo': 'decrescente',
                        'proximo': proximo
                    })
                    metadata['tipos'].append('decrescente')
            
            # Crescente por dobro
            elif b == a * 2 and c == b * 2:
                proximo = c * 2
                if 0 <= proximo <= 36:
                    scores[proximo] += 1.0
                    metadata['crescentes'].append({
                        'sequencia': [a, b, c],
                        'tipo': 'dobro',
                        'proximo': proximo
                    })
                    metadata['tipos'].append('dobro')
            
            # Crescente de terminais
            term_a, term_b, term_c = get_terminal(a), get_terminal(b), get_terminal(c)
            if term_b == (term_a + 1) % 10 and term_c == (term_b + 1) % 10:
                prox_term = (term_c + 1) % 10
                for num in range(37):
                    if get_terminal(num) == prox_term:
                        scores[num] += 0.7
                
                if not metadata['crescentes'] or metadata['crescentes'][-1]['tipo'] != 'terminal':
                    metadata['crescentes'].append({
                        'sequencia': [a, b, c],
                        'tipo': 'terminal',
                        'proximo_terminal': prox_term
                    })
                    metadata['tipos'].append('terminal')
        
        # Busca crescente de cavalos
        for i in range(len(ultimos_10) - 4):
            # Verifica se forma crescente de cavalo (2 > 5 > 8)
            seq_terms = [get_terminal(ultimos_10[j]) for j in range(i, i+3)]
            
            for cavalo in self.cavalos:
                if all(t in cavalo for t in seq_terms):
                    # É uma sequência dentro do cavalo
                    if seq_terms == sorted(seq_terms):  # Crescente
                        metadata['crescentes'].append({
                            'sequencia': ultimos_10[i:i+3],
                            'tipo': 'cavalo',
                            'cavalo': cavalo
                        })
                        metadata['tipos'].append('cavalo')
                        
                        # Sugere completar o cavalo
                        for terminal in cavalo:
                            if terminal not in seq_terms:
                                for num in range(37):
                                    if get_terminal(num) == terminal:
                                        scores[num] += 0.9
        
        return dict(scores), metadata
    
    def _detectar_retornos_duplos(self, ultimos_10: List[int]) -> Tuple[Dict[int, float], Dict]:
        """
        Detecta retornos duplos (alternância com 2+ rodadas de distância)
        
        Exemplo: 23 > X > 26 > 10 (10 retorna vizinho de 23)
        """
        scores = defaultdict(float)
        metadata = {'count': 0, 'retornos': []}
        
        for i in range(2, min(len(ultimos_10), 6)):
            atual = ultimos_10[0]
            anterior = ultimos_10[i]
            
            # Verifica se é retorno (vizinho após 2+ rodadas)
            if atual in get_vizinhos(anterior, distancia=1):
                metadata['count'] += 1
                metadata['retornos'].append({
                    'numero': anterior,
                    'retorno': atual,
                    'distancia': i,
                    'tipo': 'vizinho'
                })
                
                # Sugere outros vizinhos do anterior
                for viz in get_vizinhos(anterior, distancia=1):
                    if viz != atual:
                        scores[viz] += 0.8
            
            # Verifica retorno de espelho
            if anterior in ESPELHOS and ESPELHOS[anterior] == atual:
                metadata['count'] += 1
                metadata['retornos'].append({
                    'numero': anterior,
                    'retorno': atual,
                    'distancia': i,
                    'tipo': 'espelho'
                })
                
                # Sugere espelhos de números recentes
                for num in ultimos_10[1:4]:
                    if num in ESPELHOS:
                        scores[ESPELHOS[num]] += 0.9
        
        # Se detectou retorno duplo/triplo, reforça padrão
        if metadata['count'] >= 2:
            metadata['retorno_multiplo'] = True
            
            # Identifica números que ainda não retornaram
            for i in range(2, min(len(ultimos_10), 8)):
                num = ultimos_10[i]
                
                # Verifica se já retornou
                ja_retornou = False
                for ret in metadata['retornos']:
                    if ret['numero'] == num:
                        ja_retornou = True
                        break
                
                if not ja_retornou:
                    # Sugere retorno deste número
                    scores[num] += 1.0
                    
                    # E seus vizinhos/espelhos
                    for viz in get_vizinhos(num, distancia=1):
                        scores[viz] += 0.7
                    
                    if num in ESPELHOS:
                        scores[ESPELHOS[num]] += 0.8
        
        return dict(scores), metadata
    
    def _calcular_confianca(self, metadata: Dict) -> float:
        """
        Calcula nível de confiança baseado nos comportamentos detectados
        
        Returns:
            Float entre 0 e 1 representando confiança
        """
        confianca = 0.0
        
        # Alternância tripla é muito forte
        if metadata.get('alternancia_tripla_detectada'):
            confianca += 0.3
            if metadata.get('alternancia_detalhe', {}).get('confirmacao_vizinho'):
                confianca += 0.1
        
        # Repetições duplas
        rep_count = metadata.get('repeticoes_duplas', 0)
        if rep_count >= 2:
            confianca += 0.2
        elif rep_count == 1:
            confianca += 0.1
        
        # Cavalos incompletos
        if metadata.get('cavalos_incompletos'):
            confianca += 0.15
            if metadata.get('cavalos_detalhe', {}).get('separacao_2_rodadas'):
                confianca += 0.1
        
        # Crescentes
        if metadata.get('crescentes_detectadas'):
            confianca += 0.1 * min(len(metadata['crescentes_detectadas']), 2)
        
        # Retornos duplos
        if metadata.get('retornos_duplos', 0) >= 2:
            confianca += 0.15
        
        # Substituições
        if len(metadata.get('substituicoes_detectadas', [])) >= 2:
            confianca += 0.1
        
        # Múltiplos comportamentos é muito forte
        comportamentos_count = len(metadata.get('comportamentos_detectados', []))
        if comportamentos_count >= 4:
            confianca += 0.2
        elif comportamentos_count >= 3:
            confianca += 0.1
        
        return min(confianca, 1.0)
    
    def analyze_debug(self, ultimos_n: List[int]) -> Dict:
        """
        Versão debug com informações detalhadas
        
        Args:
            ultimos_n: Últimos N números para análise
            
        Returns:
            Dict com análise detalhada de cada comportamento
        """
        debug_info = {
            'numeros_analisados': ultimos_n,
            'terminais': [get_terminal(n) for n in ultimos_n],
            'comportamentos': {}
        }
        
        # Roda cada detector individualmente
        alt_scores, alt_meta = self._detectar_alternancia_tripla(ultimos_n, ultimos_n + list(range(37)))
        debug_info['comportamentos']['alternancia_tripla'] = {
            'scores': alt_scores,
            'metadata': alt_meta
        }
        
        rep_scores, rep_meta = self._detectar_repeticoes_duplas(ultimos_n)
        debug_info['comportamentos']['repeticoes_duplas'] = {
            'scores': rep_scores,
            'metadata': rep_meta
        }
        
        cav_scores, cav_meta = self._detectar_cavalos_incompletos(ultimos_n)
        debug_info['comportamentos']['cavalos_incompletos'] = {
            'scores': cav_scores,
            'metadata': cav_meta
        }
        
        sub_scores, sub_meta = self._detectar_substituicoes(ultimos_n, ultimos_n + list(range(37)))
        debug_info['comportamentos']['substituicoes'] = {
            'scores': sub_scores,
            'metadata': sub_meta
        }
        
        cresc_scores, cresc_meta = self._detectar_crescentes(ultimos_n)
        debug_info['comportamentos']['crescentes'] = {
            'scores': cresc_scores,
            'metadata': cresc_meta
        }
        
        ret_scores, ret_meta = self._detectar_retornos_duplos(ultimos_n)
        debug_info['comportamentos']['retornos_duplos'] = {
            'scores': ret_scores,
            'metadata': ret_meta
        }
        
        # Calcula confiança geral
        metadata_geral = {
            'alternancia_tripla_detectada': alt_meta.get('detectada', False),
            'alternancia_detalhe': alt_meta,
            'repeticoes_duplas': rep_meta.get('count', 0),
            'cavalos_incompletos': cav_meta.get('incompletos', []),
            'cavalos_detalhe': cav_meta,
            'crescentes_detectadas': cresc_meta.get('crescentes', []),
            'retornos_duplos': ret_meta.get('count', 0),
            'substituicoes_detectadas': sub_meta.get('substituicoes', []),
            'comportamentos_detectados': []
        }
        
        # Identifica comportamentos detectados
        if alt_meta.get('detectada'):
            metadata_geral['comportamentos_detectados'].append('alternancia_tripla')
        if rep_meta.get('count', 0) > 0:
            metadata_geral['comportamentos_detectados'].append('repeticoes_duplas')
        if cav_meta.get('incompletos'):
            metadata_geral['comportamentos_detectados'].append('cavalos_incompletos')
        if cresc_meta.get('crescentes'):
            metadata_geral['comportamentos_detectados'].append('crescentes')
        if ret_meta.get('count', 0) > 0:
            metadata_geral['comportamentos_detectados'].append('retornos_duplos')
        if sub_meta.get('substituicoes'):
            metadata_geral['comportamentos_detectados'].append('substituicoes')
        
        debug_info['confianca'] = self._calcular_confianca(metadata_geral)
        debug_info['comportamentos_detectados'] = metadata_geral['comportamentos_detectados']
        
        return debug_info