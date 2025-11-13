"""
patterns/validacao_ancoras.py

Validação de sinais através de confluência de múltiplas âncoras
Implementa metodologia de confirmação contextual
"""

from typing import List, Dict, Tuple, Optional
from collections import defaultdict
import logging

from utils.helpers import get_terminal, get_vizinhos
from utils.constants import ESPELHOS

logger = logging.getLogger(__name__)


class ValidadorMultiplasAncoras:
    """
    Valida sinais através de confluência de âncoras
    Um sinal só é considerado forte quando início e fim da narrativa concordam
    """
    
    def __init__(self):
        # Sistema de pontuação T vs V
        self.score_terminal = 2.0  # Relação direta (Terminal)
        self.score_vizinho = 1.5   # Relação indireta (Vizinho)
        self.min_confluencia = 1.5  # Score mínimo para confluência
        self.boost_confluencia = 1.5  # Multiplicador quando há confluência
        
    def validar_sinal(
        self,
        candidatos: Dict[int, float],
        historico: List[int],
        metadados_padroes: Dict
    ) -> Dict:
        """
        Valida sinal através de confluência de múltiplas âncoras
        
        Args:
            candidatos: Dict com scores dos candidatos
            historico: Histórico completo
            metadados_padroes: Metadados de todos os padrões
            
        Returns:
            Dict com informações de validação
        """
        # 1. Identificar estrutura narrativa
        estrutura = self._identificar_estrutura(historico[:30])
        
        if not estrutura:
            logger.warning("Não foi possível identificar estrutura narrativa")
            return {
                'confluencia_detectada': False,
                'estrutura_identificada': False
            }
        
        # 2. Extrair âncoras múltiplas
        ancora_inicio = estrutura.get('inicio')
        ancora_quebra = estrutura.get('quebra')
        ancora_desenvolvimento = estrutura.get('desenvolvimento', [])
        
        # 3. Confirmar historicamente cada âncora
        confirmacao_inicio = self._confirmar_ancora(ancora_inicio, historico)
        confirmacao_quebra = self._confirmar_ancora(ancora_quebra, historico)
        
        # 4. Verificar confluência
        confluencia = self._verificar_confluencia(
            confirmacao_inicio,
            confirmacao_quebra,
            ancora_desenvolvimento
        )
        
        # 5. Identificar números validados
        numeros_validados = []
        numeros_invalidados = []
        
        for num in candidatos:
            terminal = get_terminal(num)
            
            # Verifica se o número está nos terminais confirmados
            if confluencia['terminais_confluentes']:
                if terminal in confluencia['terminais_confluentes']:
                    numeros_validados.append(num)
                else:
                    # Verifica se é vizinho de algum terminal confluente
                    eh_vizinho_valido = False
                    for t in confluencia['terminais_confluentes']:
                        # Números do terminal confluente
                        nums_terminal = [n for n in range(37) if get_terminal(n) == t]
                        for nt in nums_terminal:
                            if num in get_vizinhos(nt, distancia=1):
                                eh_vizinho_valido = True
                                break
                    
                    if eh_vizinho_valido:
                        numeros_validados.append(num)
        
        # 6. Identificar padrões que concordam
        padroes_confluentes = self._identificar_padroes_confluentes(
            metadados_padroes,
            confluencia['terminais_confluentes']
        )
        
        # 7. Calcular força da validação
        forca_validacao = self._calcular_forca_validacao(
            confluencia,
            len(numeros_validados),
            len(padroes_confluentes)
        )
        
        return {
            'confluencia_detectada': confluencia['tem_confluencia'],
            'estrutura_identificada': True,
            'estrutura': estrutura,
            'ancora_inicio': ancora_inicio,
            'ancora_quebra': ancora_quebra,
            'confirmacao_inicio': confirmacao_inicio,
            'confirmacao_quebra': confirmacao_quebra,
            'terminais_confluentes': confluencia['terminais_confluentes'],
            'numeros_validados': numeros_validados,
            'numeros_invalidados': numeros_invalidados,
            'padroes_confluentes': padroes_confluentes,
            'boost_multiplicador': self.boost_confluencia if confluencia['tem_confluencia'] else 1.0,
            'forca_validacao': forca_validacao,
            'comportamentos_fortes': self._tem_comportamentos_fortes(metadados_padroes)
        }
    
    def _identificar_estrutura(self, historico: List[int]) -> Optional[Dict]:
        """
        Identifica estrutura narrativa: Início -> Desenvolvimento -> Quebra
        
        Args:
            historico: Últimos 30 números
            
        Returns:
            Dict com estrutura identificada ou None
        """
        if len(historico) < 10:
            return None
        
        estrutura = {
            'inicio': None,
            'desenvolvimento': [],
            'quebra': None,
            'tipo': None
        }
        
        # Busca padrão de repetição + quebra (mais comum)
        for i in range(2, min(len(historico) - 3, 15)):
            # Janela de 3 números
            janela = historico[i:i+3]
            terminais = [get_terminal(n) for n in janela]
            
            # Verifica se há repetição de terminal ou vizinho
            terminal_dominante = max(set(terminais), key=terminais.count)
            
            if terminais.count(terminal_dominante) >= 2:
                # Encontrou possível desenvolvimento
                estrutura['desenvolvimento'] = janela
                
                # Âncora de início é o primeiro dessa sequência
                estrutura['inicio'] = historico[i+2]  # Mais antigo
                
                # Busca quebra (número que não segue padrão)
                for j in range(i-1, -1, -1):
                    num_quebra = historico[j]
                    term_quebra = get_terminal(num_quebra)
                    
                    # Quebra se não é do terminal dominante nem vizinho
                    eh_vizinho = False
                    for num_dev in janela:
                        if num_quebra in get_vizinhos(num_dev, distancia=1):
                            eh_vizinho = True
                            break
                    
                    if term_quebra != terminal_dominante and not eh_vizinho:
                        estrutura['quebra'] = num_quebra
                        estrutura['tipo'] = 'repeticao_quebra'
                        return estrutura
        
        # Busca padrão de alternância (segundo mais comum)
        for i in range(len(historico) - 4):
            seq = historico[i:i+4]
            terminais = [get_terminal(n) for n in seq]
            
            # Verifica alternância (ABAB ou similar)
            if len(set(terminais)) == 2:
                t1, t2 = list(set(terminais))[:2]
                
                # Padrão alternado?
                if terminais == [t1, t2, t1, t2] or terminais == [t2, t1, t2, t1]:
                    estrutura['tipo'] = 'alternancia'
                    estrutura['desenvolvimento'] = seq[1:3]  # Meio da sequência
                    estrutura['inicio'] = seq[3]  # Mais antigo
                    estrutura['quebra'] = seq[0]  # Mais recente
                    return estrutura
        
        # Busca padrão crescente/decrescente
        for i in range(len(historico) - 3):
            a, b, c = historico[i+2], historico[i+1], historico[i]
            
            # Crescente simples
            if b == a + 1 and c == b + 1:
                estrutura['tipo'] = 'crescente'
                estrutura['desenvolvimento'] = [a, b, c]
                estrutura['inicio'] = a
                estrutura['quebra'] = historico[i-1] if i > 0 else None
                if estrutura['quebra']:
                    return estrutura
        
        # Se não encontrou padrão claro, usa heurística simples
        if len(historico) >= 7:
            estrutura['tipo'] = 'heuristica'
            estrutura['inicio'] = historico[6]  # 7º número
            estrutura['desenvolvimento'] = historico[3:6]  # Meio
            estrutura['quebra'] = historico[0]  # Mais recente
            return estrutura
        
        return None
    
    def _confirmar_ancora(self, ancora: int, historico: List[int]) -> Dict:
        """
        Confirma historicamente uma âncora usando sistema T vs V
        
        Args:
            ancora: Número âncora
            historico: Histórico completo
            
        Returns:
            Dict com scores por terminal
        """
        if ancora is None:
            return {}
        
        scores_terminal = defaultdict(float)
        ocorrencias_analisadas = 0
        
        # Busca últimas 2 ocorrências da âncora
        for i in range(10, min(len(historico), 200)):
            if historico[i] == ancora and ocorrencias_analisadas < 2:
                ocorrencias_analisadas += 1
                
                # Analisa próximos 2-3 números
                for j in range(1, min(4, len(historico) - i)):
                    num_puxado = historico[i - j]  # Lembra: histórico é invertido
                    terminal_puxado = get_terminal(num_puxado)
                    
                    # Score T (Terminal)
                    scores_terminal[terminal_puxado] += self.score_terminal
                    
                    # Score V (Vizinho)
                    for viz in get_vizinhos(num_puxado, distancia=1):
                        terminal_viz = get_terminal(viz)
                        if terminal_viz != terminal_puxado:
                            scores_terminal[terminal_viz] += self.score_vizinho
        
        # Adiciona informação intrínseca da âncora
        terminal_ancora = get_terminal(ancora)
        scores_terminal[terminal_ancora] += self.score_terminal * 0.5
        
        # Vizinhos da âncora
        for viz in get_vizinhos(ancora, distancia=1):
            terminal_viz = get_terminal(viz)
            scores_terminal[terminal_viz] += self.score_vizinho * 0.5
        
        return dict(scores_terminal)
    
    def _verificar_confluencia(
        self,
        confirmacao_inicio: Dict,
        confirmacao_quebra: Dict,
        desenvolvimento: List[int]
    ) -> Dict:
        """
        Verifica se há confluência entre âncoras
        
        Returns:
            Dict com informações de confluência
        """
        confluencia = {
            'tem_confluencia': False,
            'terminais_confluentes': [],
            'score_confluencia': 0,
            'tipo_confluencia': None
        }
        
        if not confirmacao_inicio or not confirmacao_quebra:
            return confluencia
        
        # Encontra terminais que aparecem em ambas confirmações
        terminais_comuns = set(confirmacao_inicio.keys()) & set(confirmacao_quebra.keys())
        
        for terminal in terminais_comuns:
            score_total = confirmacao_inicio[terminal] + confirmacao_quebra[terminal]
            
            if score_total >= self.min_confluencia:
                confluencia['terminais_confluentes'].append(terminal)
                confluencia['score_confluencia'] = max(
                    confluencia['score_confluencia'],
                    score_total
                )
        
        # Verifica desenvolvimento também
        if desenvolvimento:
            terminais_dev = [get_terminal(n) for n in desenvolvimento]
            terminal_dominante_dev = max(set(terminais_dev), key=terminais_dev.count)
            
            if terminal_dominante_dev in confluencia['terminais_confluentes']:
                confluencia['score_confluencia'] *= 1.2  # Boost por tripla confirmação
                confluencia['tipo_confluencia'] = 'tripla'
        
        if confluencia['terminais_confluentes']:
            confluencia['tem_confluencia'] = True
            
            # Classifica tipo de confluência
            if confluencia['score_confluencia'] >= 4.0:
                confluencia['tipo_confluencia'] = 'muito_forte'
            elif confluencia['score_confluencia'] >= 3.0:
                confluencia['tipo_confluencia'] = 'forte'
            elif confluencia['score_confluencia'] >= 2.0:
                confluencia['tipo_confluencia'] = 'moderada'
            else:
                confluencia['tipo_confluencia'] = 'fraca'
        
        return confluencia
    
    def _identificar_padroes_confluentes(
        self,
        metadados_padroes: Dict,
        terminais_confluentes: List[int]
    ) -> List[str]:
        """
        Identifica quais padrões concordam com a confluência
        
        Returns:
            Lista de nomes dos padrões confluentes
        """
        padroes_confluentes = []
        
        if not terminais_confluentes:
            return padroes_confluentes
        
        # Verifica MASTER
        if 'master' in metadados_padroes:
            # Se MASTER tem padrões nos terminais confluentes
            # (simplificado - normalmente verificaria os números específicos)
            if metadados_padroes['master'].get('padroes_encontrados', 0) > 3:
                padroes_confluentes.append('master')
        
        # Verifica ESTELAR
        if 'estelar' in metadados_padroes:
            if metadados_padroes['estelar'].get('padroes_equivalentes', 0) > 2:
                padroes_confluentes.append('estelar')
        
        # Verifica CHAIN
        if 'chain' in metadados_padroes:
            if metadados_padroes['chain'].get('compensacoes_detectadas', 0) > 0:
                padroes_confluentes.append('chain')
        
        # Verifica COMPORTAMENTOS
        if 'comportamentos' in metadados_padroes:
            if metadados_padroes['comportamentos'].get('alternancia_tripla_detectada'):
                padroes_confluentes.append('comportamentos')
            elif metadados_padroes['comportamentos'].get('cavalos_incompletos'):
                padroes_confluentes.append('comportamentos')
        
        return padroes_confluentes
    
    def _calcular_forca_validacao(
        self,
        confluencia: Dict,
        num_validados: int,
        num_padroes_confluentes: int
    ) -> float:
        """
        Calcula força da validação (0-1)
        
        Returns:
            Float representando força
        """
        forca = 0.0
        
        # Componente de confluência (40%)
        if confluencia['tem_confluencia']:
            if confluencia['tipo_confluencia'] == 'muito_forte':
                forca += 0.4
            elif confluencia['tipo_confluencia'] == 'forte':
                forca += 0.3
            elif confluencia['tipo_confluencia'] == 'moderada':
                forca += 0.2
            else:
                forca += 0.1
        
        # Componente de números validados (30%)
        if num_validados >= 5:
            forca += 0.3
        elif num_validados >= 3:
            forca += 0.2
        elif num_validados >= 1:
            forca += 0.1
        
        # Componente de padrões confluentes (30%)
        if num_padroes_confluentes >= 4:
            forca += 0.3
        elif num_padroes_confluentes >= 3:
            forca += 0.2
        elif num_padroes_confluentes >= 2:
            forca += 0.1
        elif num_padroes_confluentes >= 1:
            forca += 0.05
        
        return min(forca, 1.0)
    
    def _tem_comportamentos_fortes(self, metadados_padroes: Dict) -> bool:
        """
        Verifica se há comportamentos imediatos fortes
        
        Returns:
            Bool indicando presença de comportamentos fortes
        """
        if 'comportamentos' not in metadados_padroes:
            return False
        
        comp = metadados_padroes['comportamentos']
        
        # Alternância tripla é muito forte
        if comp.get('alternancia_tripla_detectada'):
            return True
        
        # Múltiplas repetições
        if comp.get('repeticoes_duplas', 0) >= 2:
            return True
        
        # Cavalos incompletos com confirmação
        if comp.get('cavalos_incompletos') and comp.get('cavalos_detalhe', {}).get('confirmacao_vizinho'):
            return True
        
        # Alta confiança geral
        if comp.get('nivel_confianca', 0) >= 0.7:
            return True
        
        return False
    
    def identificar_estrutura_detalhada(self, historico: List[int]) -> Dict:
        """
        Versão detalhada para debug - identifica estrutura com mais informações
        
        Args:
            historico: Histórico para análise
            
        Returns:
            Dict com estrutura detalhada
        """
        estrutura_basica = self._identificar_estrutura(historico)
        
        if not estrutura_basica:
            return {'erro': 'Não foi possível identificar estrutura'}
        
        detalhes = {
            'estrutura_basica': estrutura_basica,
            'analise_ancoras': {},
            'terminais_envolvidos': {},
            'relacoes': []
        }
        
        # Analisa cada âncora
        if estrutura_basica['inicio']:
            detalhes['analise_ancoras']['inicio'] = {
                'numero': estrutura_basica['inicio'],
                'terminal': get_terminal(estrutura_basica['inicio']),
                'vizinhos': get_vizinhos(estrutura_basica['inicio'], distancia=1),
                'espelho': ESPELHOS.get(estrutura_basica['inicio']),
                'confirmacao': self._confirmar_ancora(estrutura_basica['inicio'], historico)
            }
        
        if estrutura_basica['quebra']:
            detalhes['analise_ancoras']['quebra'] = {
                'numero': estrutura_basica['quebra'],
                'terminal': get_terminal(estrutura_basica['quebra']),
                'vizinhos': get_vizinhos(estrutura_basica['quebra'], distancia=1),
                'espelho': ESPELHOS.get(estrutura_basica['quebra']),
                'confirmacao': self._confirmar_ancora(estrutura_basica['quebra'], historico)
            }
        
        # Analisa desenvolvimento
        if estrutura_basica['desenvolvimento']:
            terminais_dev = [get_terminal(n) for n in estrutura_basica['desenvolvimento']]
            detalhes['terminais_envolvidos']['desenvolvimento'] = terminais_dev
            
            # Identifica relações
            for i in range(len(estrutura_basica['desenvolvimento']) - 1):
                n1 = estrutura_basica['desenvolvimento'][i]
                n2 = estrutura_basica['desenvolvimento'][i + 1]
                
                relacao = {
                    'numeros': (n1, n2),
                    'tipo': self._identificar_relacao(n1, n2)
                }
                detalhes['relacoes'].append(relacao)
        
        # Verifica confluência
        if 'inicio' in detalhes['analise_ancoras'] and 'quebra' in detalhes['analise_ancoras']:
            detalhes['confluencia'] = self._verificar_confluencia(
                detalhes['analise_ancoras']['inicio']['confirmacao'],
                detalhes['analise_ancoras']['quebra']['confirmacao'],
                estrutura_basica['desenvolvimento']
            )
        
        return detalhes
    
    def _identificar_relacao(self, n1: int, n2: int) -> str:
        """
        Identifica tipo de relação entre dois números
        
        Returns:
            String descrevendo relação
        """
        # Terminal igual?
        if get_terminal(n1) == get_terminal(n2):
            return 'mesmo_terminal'
        
        # Vizinhos?
        if n2 in get_vizinhos(n1, distancia=1):
            return 'vizinhos'
        
        # Espelhos?
        if n1 in ESPELHOS and ESPELHOS[n1] == n2:
            return 'espelhos'
        
        # Crescente/Decrescente?
        if n2 == n1 + 1:
            return 'crescente'
        elif n2 == n1 - 1:
            return 'decrescente'
        
        # Dobro/Metade?
        if n2 == n1 * 2:
            return 'dobro'
        elif n1 == n2 * 2:
            return 'metade'
        
        # Soma igual?
        soma1 = sum(int(d) for d in str(n1))
        soma2 = sum(int(d) for d in str(n2))
        if soma1 == soma2:
            return 'mesma_soma'
        
        return 'sem_relacao_direta'