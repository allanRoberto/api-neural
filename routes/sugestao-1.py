"""
routes/sugestao.py

Rota para sugestões com Ensemble MASTER + ESTELAR + CHAIN + TEMPORAL + COMPORTAMENTOS IMEDIATOS
Inclui validação por múltiplas âncoras e proteções dinâmicas
"""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict
import logging
from datetime import datetime, timedelta

# Importação dos padrões existentes
from patterns.master import PatternMaster
from patterns.estelar import PatternEstelar
from patterns.chain import ChainAnalyzer
from patterns.temporal import TemporalPattern

# 🆕 NOVOS PADRÕES
from patterns.comportamentos_imediatos import ComportamentosImediatos
from patterns.validacao_ancoras import ValidadorMultiplasAncoras

from utils.constants import ESPELHOS
from utils.helpers import get_vizinhos
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

router = APIRouter()
logger = logging.getLogger(__name__)


async def _get_historico_interno(request: Request, roulette_id: str, limit: int = 500):
    """
    Função auxiliar para buscar histórico (reutilizável)
    
    Args:
        request: Request FastAPI
        roulette_id: ID da roleta
        limit: Quantidade de números
    
    Returns:
        Lista de números
    
    Raises:
        HTTPException: Se houver erro ou histórico insuficiente
    """
    try:
        db = request.app.state.db
        settings = request.app.state.settings
        collection = db[settings.MONGODB_COLLECTION]
        
        cursor = collection.find(
            {"roulette_id": roulette_id}
        ).sort("timestamp", -1).limit(limit)
        
        documents = await cursor.to_list(length=limit)
        
        if len(documents) < 10:
            raise HTTPException(
                status_code=400,
                detail=f"Histórico insuficiente: {len(documents)} números (mínimo 10)"
            )
        
        # Extrair números (campo 'value')
        numeros = [doc.get("value", 0) for doc in documents]
        
        return numeros
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar histórico: {str(e)}"
        )


def ajustar_pesos_dinamicamente(metadados: Dict) -> Dict[str, float]:
    """
    🆕 Ajusta pesos baseado na força de cada padrão
    
    Args:
        metadados: Metadados de todos os padrões
    
    Returns:
        Dict com pesos ajustados e normalizados
    """
    # Pesos base
    pesos = {
        'master': 0.15,
        'estelar': 0.15,
        'chain': 0.15,
        'temporal': 0.55,
        'comportamentos': 0.10  # Base mais alta para padrões quentes
    }
    
    # Se comportamentos imediatos detectou alternância tripla
    if metadados.get('comportamentos', {}).get('alternancia_tripla_detectada'):
        pesos['comportamentos'] = 0.40
        logger.info("Alternância tripla detectada - aumentando peso de comportamentos")
    
    # Se detectou cavalos incompletos
    if metadados.get('comportamentos', {}).get('cavalos_incompletos'):
        pesos['comportamentos'] *= 1.2
    
    # Se múltiplas âncoras confirmam
    if metadados.get('validacao', {}).get('confluencia_detectada'):
        padroes_confluentes = metadados.get('validacao', {}).get('padroes_confluentes', [])
        for padrao in padroes_confluentes:
            if padrao in pesos:
                pesos[padrao] *= 1.3
                logger.info(f"Confluência detectada - aumentando peso de {padrao}")
    
    # Se CHAIN tem muitas cadeias aprendidas
    if metadados.get('chain', {}).get('total_cadeias_aprendidas', 0) > 10:
        pesos['chain'] *= 1.2
    
    # Se MASTER tem padrões fortes
    if metadados.get('master', {}).get('padroes_encontrados', 0) > 5:
        pesos['master'] *= 1.15
    
    # Normaliza pesos para somar 1.0
    total = sum(pesos.values())
    return {k: v/total for k, v in pesos.items()}


def calcular_ensemble(
    resultado_master,
    resultado_estelar,
    resultado_chain,
    resultado_temporal,
    resultado_comportamentos,
    w_master: float = 0.15,
    w_estelar: float = 0.15,
    w_chain: float = 0.15,
    w_temporal: float = 0.30,
    w_comportamentos: float = 0.20
) -> Dict[int, float]:
    """
    Combina scores dos 6 padrões com pesos configuráveis
    
    Args:
        resultado_master: PatternResult do MASTER
        resultado_estelar: PatternResult do ESTELAR
        resultado_chain: PatternResult do CHAIN
        resultado_temporal: Tuple (candidates, metadata) do TEMPORAL
        resultado_comportamentos: PatternResult do COMPORTAMENTOS IMEDIATOS
        w_master: Peso do MASTER (0-1)
        w_estelar: Peso do ESTELAR (0-1)
        w_chain: Peso do CHAIN (0-1)
        w_temporal: Peso do TEMPORAL (0-1)
        w_comportamentos: Peso do COMPORTAMENTOS (0-1)
    
    Returns:
        Dict {numero: score_combinado} normalizado
    """
    # TEMPORAL retorna (candidates, metadata) - extrair
    temporal_candidates = resultado_temporal[0] if isinstance(resultado_temporal, tuple) else {}
    temporal_metadata = resultado_temporal[1] if isinstance(resultado_temporal, tuple) else {}
    
    # Normaliza pesos
    total_peso = w_master + w_estelar + w_chain + w_temporal + w_comportamentos
    w_master /= total_peso
    w_estelar /= total_peso
    w_chain /= total_peso
    w_temporal /= total_peso
    w_comportamentos /= total_peso
    
    # Combina scores
    scores_combinados = defaultdict(float)
    
    # MASTER
    for num, score in resultado_master.scores.items():
        scores_combinados[num] += w_master * score
    
    # ESTELAR
    for num, score in resultado_estelar.scores.items():
        scores_combinados[num] += w_estelar * score
    
    # CHAIN
    for num, score in resultado_chain.scores.items():
        scores_combinados[num] += w_chain * score
    
    # TEMPORAL (usa candidates dict diretamente)
    for num, score in temporal_candidates.items():
        scores_combinados[num] += w_temporal * score
    
    # 🆕 COMPORTAMENTOS IMEDIATOS
    for num, score in resultado_comportamentos.scores.items():
        scores_combinados[num] += w_comportamentos * score
    
    # Normaliza resultado final
    if scores_combinados:
        max_score = max(scores_combinados.values())
        if max_score > 0:
            scores_combinados = {
                num: score / max_score
                for num, score in scores_combinados.items()
            }
    
    return dict(scores_combinados)


def aplicar_validacao_ancoras(
    scores_ensemble: Dict[int, float],
    numeros: List[int],
    metadados_padroes: Dict,
    validador: ValidadorMultiplasAncoras
) -> Tuple[Dict[int, float], Dict]:
    """
    🆕 Aplica validação por múltiplas âncoras e ajusta scores
    
    Args:
        scores_ensemble: Scores do ensemble
        numeros: Histórico completo
        metadados_padroes: Metadados de todos os padrões
        validador: Instância do validador
    
    Returns:
        Tuple (scores_ajustados, informacoes_validacao)
    """
    # Valida sinal através de confluência
    validacao = validador.validar_sinal(
        scores_ensemble,
        numeros,
        metadados_padroes
    )
    
    scores_ajustados = scores_ensemble.copy()
    
    # Se há confluência, aplica boost
    if validacao.get('confluencia_detectada', False):
        boost = validacao.get('boost_multiplicador', 1.5)
        for num in validacao.get('numeros_validados', []):
            if num in scores_ajustados:
                scores_ajustados[num] *= boost
                logger.info(f"Boost de {boost}x aplicado ao número {num} por confluência")
    
    # Penaliza números que falharam na validação
    for num in validacao.get('numeros_invalidados', []):
        if num in scores_ajustados:
            scores_ajustados[num] *= 0.5
            logger.info(f"Penalização aplicada ao número {num} por falta de confluência")
    
    return scores_ajustados, validacao


def calcular_consenso_avancado(
    candidatos_top: List[int],
    resultado_master,
    resultado_estelar,
    resultado_chain,
    resultado_temporal,
    resultado_comportamentos,  # 🆕
    validacao_ancoras: Dict  # 🆕
) -> Dict:
    """
    🆕 Consenso avançado considerando 6 padrões + validação por âncoras
    
    Returns:
        Dict com níveis de consenso e confirmação
    """
    # Extrai top candidatos de cada padrão
    top_master = [num for num, _ in resultado_master.get_top_n(10)]
    top_estelar = [num for num, _ in resultado_estelar.get_top_n(10)]
    top_chain = [num for num, _ in resultado_chain.get_top_n(10)]
    top_temporal = list(resultado_temporal[0].keys())[:10] if isinstance(resultado_temporal, tuple) else []
    top_comportamentos = [num for num, _ in resultado_comportamentos.get_top_n(10)]
    
    # Números validados por âncoras
    validados_ancoras = validacao_ancoras.get('numeros_validados', [])
    
    consenso = {
        # Níveis de confirmação hierárquicos
        'nivel_1_exato': [],           # MASTER confirma exatamente
        'nivel_2_terminal': [],        # Comportamentos imediatos (terminal/alternância)
        'nivel_3_equivalente': [],     # ESTELAR (vizinho/espelho/soma)
        'nivel_4_contextual': [],      # CHAIN (faltante/compensação)
        'nivel_5_temporal': [],        # TEMPORAL (mesmo horário)
        
        # Consenso múltiplo (6 padrões)
        'consenso_total': [],          # Todos os 6 concordam
        'consenso_quintuplo': {},      # 5 de 6 concordam
        'consenso_quadruplo': {},      # 4 de 6 concordam
        'consenso_triplo': {},         # 3 de 6 concordam
        'consenso_duplo': {},          # 2 de 6 concordam
        'unicos': {},                  # Apenas 1 padrão sugere
        
        # 🆕 Validação por âncoras
        'confluencia_total': [],       # Validados por múltiplas âncoras
        'forca_maxima': []            # Consenso total + confluência
    }
    
    # Para cada candidato top
    for num in candidatos_top:
        # Conta em quantos padrões aparece
        contagem = 0
        padroes_presentes = []
        
        if num in top_master:
            contagem += 0.5
            padroes_presentes.append('master')
            consenso['nivel_1_exato'].append(num)
            
        if num in top_estelar:
            contagem += 0.3
            padroes_presentes.append('estelar')
            consenso['nivel_3_equivalente'].append(num)
            
        if num in top_chain:
            contagem += 0.2
            padroes_presentes.append('chain')
            consenso['nivel_4_contextual'].append(num)
            
            
        if num in top_temporal:
            contagem += 1
            padroes_presentes.append('temporal')
            consenso['nivel_5_temporal'].append(num)
            
        if num in top_comportamentos:
            contagem += 0.5
            padroes_presentes.append('comportamentos')
            consenso['nivel_2_terminal'].append(num)
        
        # Classifica por nível de consenso
        tipo_consenso = "_".join(sorted(padroes_presentes))
        
        if contagem == 6:
            consenso['consenso_total'].append(num)
            if num in validados_ancoras:
                consenso['forca_maxima'].append(num)
                
        elif contagem == 5:
            consenso['consenso_quintuplo'][tipo_consenso] = consenso['consenso_quintuplo'].get(tipo_consenso, [])
            consenso['consenso_quintuplo'][tipo_consenso].append(num)
            
        elif contagem == 4:
            consenso['consenso_quadruplo'][tipo_consenso] = consenso['consenso_quadruplo'].get(tipo_consenso, [])
            consenso['consenso_quadruplo'][tipo_consenso].append(num)
            
        elif contagem == 3:
            consenso['consenso_triplo'][tipo_consenso] = consenso['consenso_triplo'].get(tipo_consenso, [])
            consenso['consenso_triplo'][tipo_consenso].append(num)
            
        elif contagem == 2:
            consenso['consenso_duplo'][tipo_consenso] = consenso['consenso_duplo'].get(tipo_consenso, [])
            consenso['consenso_duplo'][tipo_consenso].append(num)
            
        elif contagem == 1:
            consenso['unicos'][tipo_consenso] = consenso['unicos'].get(tipo_consenso, [])
            consenso['unicos'][tipo_consenso].append(num)
        
        # Adiciona à confluência se validado por âncoras
        if num in validados_ancoras:
            consenso['confluencia_total'].append(num)
    
    return consenso


def identificar_comportamento_dominante(metadados: Dict) -> Dict:
    """
    🆕 Identifica qual comportamento está dominando a mesa
    
    Args:
        metadados: Metadados de todos os padrões
    
    Returns:
        Dict com comportamento dominante e força
    """
    comportamentos = {
        'alternancia': 0,
        'repeticao': 0,
        'crescente': 0,
        'compensacao': 0,
        'substituicao': 0,
        'faltante': 0
    }
    
    # Analisa metadados de comportamentos imediatos
    if metadados.get('comportamentos', {}).get('alternancia_tripla_detectada'):
        comportamentos['alternancia'] += 3
    
    if metadados.get('comportamentos', {}).get('repeticoes_duplas', 0) > 0:
        comportamentos['repeticao'] += metadados['comportamentos']['repeticoes_duplas']
    
    if len(metadados.get('comportamentos', {}).get('crescentes_detectadas', [])) > 0:
        comportamentos['crescente'] += 2
    
    # Analisa CHAIN
    if metadados.get('chain', {}).get('compensacoes_detectadas', 0) > 0:
        comportamentos['compensacao'] += metadados['chain']['compensacoes_detectadas']
    
    if metadados.get('chain', {}).get('inversoes_detectadas', 0) > 0:
        comportamentos['alternancia'] += 1
    
    # Analisa ESTELAR
    if metadados.get('estelar', {}).get('padroes_equivalentes', 0) > 3:
        comportamentos['substituicao'] += 2
    
    # Identifica dominante
    dominante = max(comportamentos, key=comportamentos.get)
    forca = comportamentos[dominante]
    
    return {
        'tipo': dominante,
        'forca': forca,
        'descricao': _get_descricao_comportamento(dominante),
        'scores': comportamentos
    }


def _get_descricao_comportamento(tipo: str) -> str:
    """Retorna descrição do comportamento dominante"""
    descricoes = {
        'alternancia': 'Mesa alternando entre terminais/setores',
        'repeticao': 'Mesa repetindo padrões exatos ou vizinhos',
        'crescente': 'Mesa em sequência crescente/decrescente',
        'compensacao': 'Mesa pagando números faltantes',
        'substituicao': 'Mesa substituindo por equivalentes',
        'faltante': 'Mesa com números atrasados para pagar'
    }
    return descricoes.get(tipo, 'Comportamento misto')


def calcular_forca_sinal(validacao: Dict, consenso: Dict) -> Dict:
    """
    🆕 Calcula força do sinal baseado em múltiplos fatores
    
    Returns:
        Dict com força e componentes
    """
    forca = 0
    componentes = []
    
    # Confluência de âncoras (máximo peso)
    if validacao.get('confluencia_detectada'):
        forca += 40
        componentes.append('confluencia_ancoras')
    
    # Consenso total (6/6)
    if consenso.get('consenso_total'):
        forca += 30
        componentes.append('consenso_total')
    
    # Consenso quíntuplo (5/6)
    elif consenso.get('consenso_quintuplo'):
        forca += 25
        componentes.append('consenso_quintuplo')
    
    # Força máxima (confluência + consenso)
    if consenso.get('forca_maxima'):
        forca += 20
        componentes.append('forca_maxima')
    
    # Comportamentos imediatos detectados
    if validacao.get('comportamentos_fortes'):
        forca += 15
        componentes.append('comportamentos_imediatos')
    
    # Classificação da força
    if forca >= 70:
        classificacao = 'MUITO_FORTE'
        confianca = 0.9
    elif forca >= 50:
        classificacao = 'FORTE'
        confianca = 0.75
    elif forca >= 30:
        classificacao = 'MODERADA'
        confianca = 0.6
    else:
        classificacao = 'FRACA'
        confianca = 0.4
    
    return {
        'valor': forca,
        'classificacao': classificacao,
        'confianca': confianca,
        'componentes': componentes
    }


def gerar_recomendacao(forca_sinal: Dict, comportamento: Dict) -> Dict:
    """
    🆕 Gera recomendação baseada na força do sinal
    
    Returns:
        Dict com recomendação e estratégia
    """
    classificacao = forca_sinal['classificacao']
    comportamento_tipo = comportamento['tipo']
    
    recomendacoes = {
        'MUITO_FORTE': {
            'acao': 'ENTRADA_MAXIMA',
            'descricao': 'Sinal muito forte com múltiplas confirmações',
            'cobertura': 'Apostar nos principais + proteções completas',
            'gestao': 'Até 3 tentativas com progressão moderada'
        },
        'FORTE': {
            'acao': 'ENTRADA_CONFIANTE',
            'descricao': 'Sinal forte com boa confluência',
            'cobertura': 'Apostar nos top 6-8 números',
            'gestao': 'Até 2 tentativas com gestão conservadora'
        },
        'MODERADA': {
            'acao': 'ENTRADA_CAUTELOSA',
            'descricao': 'Sinal moderado, aguardar confirmação',
            'cobertura': 'Apostar apenas top 4-5 números',
            'gestao': 'Apenas 1 tentativa, sem progressão'
        },
        'FRACA': {
            'acao': 'AGUARDAR',
            'descricao': 'Sinal fraco, melhor aguardar próximo ciclo',
            'cobertura': 'Não recomendado apostar',
            'gestao': 'Observar evolução do padrão'
        }
    }
    
    rec = recomendacoes[classificacao]
    rec['comportamento_detectado'] = comportamento_tipo
    rec['estrategia_especifica'] = _get_estrategia_por_comportamento(comportamento_tipo)
    
    return rec


def _get_estrategia_por_comportamento(tipo: str) -> str:
    """Retorna estratégia específica por comportamento"""
    estrategias = {
        'alternancia': 'Focar em terminais opostos ao último',
        'repeticao': 'Priorizar números exatos e vizinhos',
        'crescente': 'Apostar na continuação da sequência',
        'compensacao': 'Focar nos números faltantes identificados',
        'substituicao': 'Incluir espelhos e equivalentes',
        'faltante': 'Aguardar momento de pagamento do atraso'
    }
    return estrategias.get(tipo, 'Manter estratégia balanceada')


def aplicar_protecoes(
    candidatos_base: List[int],
    historico: List[int],
    incluir_zero: bool = True,
    incluir_espelhos: bool = True,
    incluir_vizinhos: bool = True,
    incluir_cavalos: bool = True,  # 🆕
    max_protecoes: int = 8  # Aumentado
) -> Dict[str, List[int]]:
    """
    Adiciona proteções aos candidatos base (versão melhorada)
    
    Args:
        candidatos_base: Lista de números principais
        historico: Histórico completo
        incluir_zero: Incluir o número 0
        incluir_espelhos: Incluir espelhos dos candidatos
        incluir_vizinhos: Incluir vizinhos dos candidatos
        incluir_cavalos: Incluir completação de cavalos
        max_protecoes: Máximo de proteções adicionais
    
    Returns:
        Dict com candidatos e proteções separados
    """
    protecoes = set()
    
    # 1. ZERO (sempre importante)
    if incluir_zero and 0 not in candidatos_base:
        protecoes.add(0)
    
    # 2. ESPELHOS dos candidatos
    if incluir_espelhos:
        for num in candidatos_base:
            if num in ESPELHOS:
                espelho = ESPELHOS[num]
                if espelho not in candidatos_base:
                    protecoes.add(espelho)
    
    # 3. VIZINHOS (1 de cada lado na roda)
    if incluir_vizinhos:
        for num in candidatos_base:
            vizinhos = get_vizinhos(num, distancia=1)
            for viz in vizinhos[:2]:  # Só os 2 mais próximos
                if viz not in candidatos_base and viz not in protecoes:
                    protecoes.add(viz)
    
    # 4. 🆕 COMPLETAR CAVALOS
    if incluir_cavalos:
        cavalos = [
            [2, 5, 8], [3, 6, 9], [1, 4, 7]
        ]
        
        for cavalo in cavalos:
            presentes = [n for n in cavalo if n in candidatos_base]
            if len(presentes) == 2:
                # 2 de 3 presentes, adiciona o faltante
                faltante = [n for n in cavalo if n not in candidatos_base][0]
                if faltante not in protecoes:
                    protecoes.add(faltante)
                    logger.info(f"Completando cavalo {cavalo} com {faltante}")
    
    # 5. COMPLETAR RUAS (se 2 de 3 presentes)
    ruas = [
        [1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12],
        [13, 14, 15], [16, 17, 18], [19, 20, 21], [22, 23, 24],
        [25, 26, 27], [28, 29, 30], [31, 32, 33], [34, 35, 36]
    ]
    
    for rua in ruas:
        presentes = [n for n in rua if n in candidatos_base]
        if len(presentes) == 2:
            faltante = [n for n in rua if n not in candidatos_base][0]
            if faltante not in protecoes:
                protecoes.add(faltante)
    
    # 6. FAMÍLIA DE DEZENAS
    for terminal in range(10):
        familia = [n for n in [terminal, 10+terminal, 20+terminal, 30+terminal] 
                   if 0 <= n <= 36]
        presentes = [n for n in familia if n in candidatos_base]
        
        if len(presentes) >= 2:
            for num in familia:
                if num not in candidatos_base and num not in protecoes:
                    protecoes.add(num)
    
    
    
    # Limitar proteções
    protecoes_list = list(protecoes)[:max_protecoes]
    
    return {
        'candidatos': candidatos_base,
        'protecoes': protecoes_list,
        'total_protegido': len(candidatos_base) + len(protecoes_list)
    }


def identificar_faltantes(candidatos: List[int], historico: List[int], window: int = 30) -> List[int]:
    """
    Identifica números faltantes (não apareceram recentemente)
    
    Args:
        candidatos: Lista de candidatos
        historico: Histórico completo
        window: Janela de análise
    
    Returns:
        Lista de números faltantes entre os candidatos
    """
    recentes = set(historico[:window])
    faltantes = [num for num in candidatos if num not in recentes]
    return faltantes


def _get_consenso_nivel(numero: int, consenso: Dict) -> str:
    """Retorna nível de consenso de um número (6 padrões + confluência)"""
    
    # Força máxima (consenso + confluência)
    if numero in consenso.get('forca_maxima', []):
        return "forca_maxima_6/6+ancoras"
    
    # Consenso total (6/6)
    if numero in consenso.get('consenso_total', []):
        return "total_6/6"
    
    # Confluência de âncoras
    if numero in consenso.get('confluencia_total', []):
        return "confluencia_ancoras"
    
    # Consenso quíntuplo (5/6)
    for tipo, nums in consenso.get('consenso_quintuplo', {}).items():
        if numero in nums:
            return f"quintuplo_{tipo}"
    
    # Consenso quádruplo (4/6)
    for tipo, nums in consenso.get('consenso_quadruplo', {}).items():
        if numero in nums:
            return f"quadruplo_{tipo}"
    
    # Consenso triplo (3/6)
    for tipo, nums in consenso.get('consenso_triplo', {}).items():
        if numero in nums:
            return f"triplo_{tipo}"
    
    # Consenso duplo (2/6)
    for tipo, nums in consenso.get('consenso_duplo', {}).items():
        if numero in nums:
            return f"duplo_{tipo}"
    
    # Único (1/6)
    for tipo, nums in consenso.get('unicos', {}).items():
        if numero in nums:
            return f"unico_{tipo}"
    
    return "ensemble"


def _get_tipo_protecao(numero: int, candidatos: List[int], historico: List[int]) -> str:
    """Identifica tipo de proteção (versão melhorada)"""
    tipos = []
    
    if numero == 0:
        tipos.append("zero")
    
    # Verifica se é espelho
    for cand in candidatos:
        if cand in ESPELHOS and ESPELHOS[cand] == numero:
            tipos.append(f"espelho_de_{cand}")
            break
    
    # Verifica se é vizinho
    for cand in candidatos:
        vizinhos = get_vizinhos(cand, distancia=1)
        if numero in vizinhos:
            tipos.append(f"vizinho_de_{cand}")
            break
    
    # 🆕 Verifica se completa cavalo
    cavalos = [[2, 5, 8], [3, 6, 9], [1, 4, 7]]
    for cavalo in cavalos:
        if numero in cavalo:
            presentes = [n for n in cavalo if n in candidatos]
            if len(presentes) == 2 and numero not in candidatos:
                tipos.append(f"completa_cavalo_{cavalo}")
                break
    
    # Verifica se completa rua
    ruas = [
        [1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12],
        [13, 14, 15], [16, 17, 18], [19, 20, 21], [22, 23, 24],
        [25, 26, 27], [28, 29, 30], [31, 32, 33], [34, 35, 36]
    ]
    
    for rua in ruas:
        if numero in rua:
            presentes = [n for n in rua if n in candidatos]
            if len(presentes) == 2:
                tipos.append(f"completa_rua_{rua}")
                break
    
    return ", ".join(tipos) if tipos else "protecao_geral"


@router.get("/{roulette_id}")
async def sugestao(
    request: Request,
    roulette_id: str,
    quantidade: int = Query(6, ge=1, le=15, description="Quantidade de números sugeridos"),
    incluir_protecoes: bool = Query(True, description="Incluir proteções"),
    incluir_zero: bool = Query(True, description="Incluir zero nas proteções"),
    max_protecoes: int = Query(8, ge=0, le=12, description="Máximo de proteções"),
    
    # Pesos dos padrões (ajustáveis)
    w_master: float = Query(0.15, ge=0, le=1, description="Peso MASTER"),
    w_estelar: float = Query(0.15, ge=0, le=1, description="Peso ESTELAR"),
    w_chain: float = Query(0.15, ge=0, le=1, description="Peso CHAIN"),
    w_temporal: float = Query(0.10, ge=0, le=1, description="Peso TEMPORAL"),
    w_comportamentos: float = Query(0.30, ge=0, le=1, description="Peso COMPORTAMENTOS"),

    target_time: str = Query(None, description="Horário alvo para análise temporal"),
    interval_minutes: int = Query(5, ge=1, le=30, description="Intervalo em minutos para análise temporal"),
    days_back: int = Query(30, ge=7, le=90, description="Dias para análise temporal"),


    # Configurações avançadas
    usar_pesos_dinamicos: bool = Query(True, description="Ajustar pesos dinamicamente"),
    validar_ancoras: bool = Query(True, description="Usar validação por múltiplas âncoras"),
    min_confianca: float = Query(0.5, ge=0, le=1, description="Confiança mínima para sugestão")
):
    """
    Endpoint principal para sugestões com ensemble de 6 padrões
    Inclui comportamentos imediatos e validação por múltiplas âncoras
    
    Args:
        roulette_id: ID da roleta
        quantidade: Quantidade de números principais
        incluir_protecoes: Se deve incluir proteções
        incluir_zero: Se deve incluir 0 nas proteções
        max_protecoes: Máximo de proteções adicionais
        w_master: Peso do padrão MASTER
        w_estelar: Peso do padrão ESTELAR
        w_chain: Peso do padrão CHAIN
        w_temporal: Peso do padrão TEMPORAL
        w_comportamentos: Peso do padrão COMPORTAMENTOS
        target_time: Horário alvo para análise temporal
        interval_minutes: Intervalo em minutos
        days_back: Dias para análise temporal
        usar_pesos_dinamicos: Se deve ajustar pesos dinamicamente
        validar_ancoras: Se deve usar validação por múltiplas âncoras
        min_confianca: Confiança mínima para gerar sugestão
    
    Returns:
        JSON com sugestões, análise e métricas
    """
    try:
        # Busca histórico
        numeros = await _get_historico_interno(request, roulette_id, limit=200)
        logger.info(f"Analisando {len(numeros)} números para {roulette_id}")
        
        TEMPORAL_CONFIG = {
            "api_base_url": "https://api.revesbot.com.br",
            "interval_minutes": 2,
            "days_back": days_back,
            "min_occurrences": 2,
            "roulette_id": roulette_id
        }


        config_master = {
            'enable_combined': False,     # Habilita D1Par, D2Ímpar, etc
            'enable_blocks': False,       # Habilita bloqueios (ciclo exausto)
            'cycle_detection': False,     # Detecta ciclos completos
            'verbose': False             # Modo silencioso
        }

        config_estelar = {
        'max_gap_between_elements': 2,
        'memory_short': 50,
        'memory_long': 200,
        'enable_inversions': True,
        'enable_compensation': True,
        'verbose': False,
        'equivalence_weights': {
            'EXACT': 1.0,
            'NEIGHBOR': 0.5,
            'TERMINAL': 0.4,
            'MIRROR': 0.9,
            'PROPERTY': 0.5,
            'BEHAVIORAL': 0.7
        }
        }

        config_chain = {
            "min_chain_support": 2,
            "chain_decay": 0.75,
            "recent_window_miss": 30,
            "max_chain_length": 4
        }
        # Inicializa padrões - TODOS seguem o mesmo padrão!
        master = PatternMaster(config=config_master)

        estelar = PatternEstelar(config=config_estelar)
        chain = ChainAnalyzer(config=config_chain)
        temporal = TemporalPattern(**TEMPORAL_CONFIG)  # Inicialização padrão como TODOS os outros!
        comportamentos = ComportamentosImediatos()
        validador = ValidadorMultiplasAncoras()
        
        # Análise dos 6 padrões - TODOS usam analyze()!
        resultado_master = master.analyze(numeros)
        resultado_estelar = estelar.analyze(numeros)
        resultado_chain = chain.analyze(numeros)
        resultado_comportamentos = comportamentos.analyze(numeros)
        resultado_temporal = await temporal.analyze(numeros)  # MESMO PADRÃO!
             
        # Coleta todos os metadados
        metadados_completos = {
            'master': resultado_master.metadata,
            'estelar': resultado_estelar.metadata,
            'chain': resultado_chain.metadata,
            'temporal': resultado_temporal[1] if isinstance(resultado_temporal, tuple) else {},
            'comportamentos': resultado_comportamentos.metadata
        }
        
        # 🆕 Ajuste dinâmico de pesos (se habilitado)
        if usar_pesos_dinamicos:
            pesos_ajustados = ajustar_pesos_dinamicamente(metadados_completos)
            w_master = pesos_ajustados['master']
            w_estelar = pesos_ajustados['estelar']
            w_chain = pesos_ajustados['chain']
            w_temporal = pesos_ajustados['temporal']
            w_comportamentos = pesos_ajustados['comportamentos']
            logger.info(f"Pesos ajustados dinamicamente: {pesos_ajustados}")
        
        # Calcula ensemble com 6 padrões
        scores_ensemble = calcular_ensemble(
            resultado_master,
            resultado_estelar,
            resultado_chain,
            resultado_temporal,
            resultado_comportamentos,  # 🆕
            w_master=w_master,
            w_estelar=w_estelar,
            w_chain=w_chain,
            w_temporal=w_temporal,
            w_comportamentos=w_comportamentos  # 🆕
        )
        
        # 🆕 Validação por múltiplas âncoras (se habilitada)
        info_validacao = {}
        if validar_ancoras:
            scores_ensemble, info_validacao = aplicar_validacao_ancoras(
                scores_ensemble,
                numeros,
                metadados_completos,
                validador
            )
            metadados_completos['validacao'] = info_validacao
        
        # Ordena candidatos
        candidatos_ordenados = sorted(
            scores_ensemble.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Pega top N
        candidatos_top = [num for num, _ in candidatos_ordenados[:quantidade]]
        
        # Identifica faltantes
        faltantes = identificar_faltantes(candidatos_top, numeros, window=30)
        
        # 🆕 Calcula consenso avançado
        consenso = calcular_consenso_avancado(
            candidatos_top,
            resultado_master,
            resultado_estelar,
            resultado_chain,
            resultado_temporal,
            resultado_comportamentos,
            info_validacao
        )
        
        # 🆕 Identifica comportamento dominante
        comportamento_dominante = identificar_comportamento_dominante(metadados_completos)
        
        # 🆕 Calcula força do sinal
        forca_sinal = calcular_forca_sinal(info_validacao, consenso)
        
        # 🆕 Gera recomendação
        recomendacao = gerar_recomendacao(forca_sinal, comportamento_dominante)
        
        # 🆕 Verifica confiança mínima
        if forca_sinal['confianca'] < min_confianca:
            logger.warning(f"Confiança {forca_sinal['confianca']} abaixo do mínimo {min_confianca}")
            # Ainda gera resposta mas com aviso
            recomendacao['aviso'] = f"Confiança abaixo do mínimo configurado ({min_confianca})"
        
        # Aplica proteções
        if incluir_protecoes:
            protecoes_result = aplicar_protecoes(
                candidatos_top,
                numeros,
                incluir_zero=incluir_zero,
                incluir_espelhos=True,
                incluir_vizinhos=True,
                incluir_cavalos=True,  # 🆕
                max_protecoes=max_protecoes
            )
        else:
            protecoes_result = {
                'candidatos': candidatos_top,
                'protecoes': [],
                'total_protegido': len(candidatos_top)
            }
        
        # Constrói resposta completa
        resposta = {
            "roulette_id": roulette_id,
            "timestamp": datetime.now().isoformat(),
            "ultimo_numero": numeros[0] if numeros else None,
            
            "sugestoes": {
                "principais": [
                    {
                        "numero": num,
                        "score": round(scores_ensemble[num], 6),
                        "ranking": i + 1,
                        "faltante": num in faltantes,
                        "consenso": _get_consenso_nivel(num, consenso),
                        "validado_ancoras": num in info_validacao.get('numeros_validados', [])  # 🆕
                    }
                    for i, num in enumerate(candidatos_top)
                ],
                "protecoes": [
                    {
                        "numero": num,
                        "tipo": _get_tipo_protecao(num, candidatos_top, numeros)
                    }
                    for num in protecoes_result['protecoes']
                ],
                "total_numeros": protecoes_result['total_protegido']
            },
            
            "analise": {
                "consenso": consenso,
                "faltantes": faltantes,
                "ultimos_10": numeros[:10],
                "comportamento_dominante": comportamento_dominante,  # 🆕
                "forca_sinal": forca_sinal,  # 🆕
                "recomendacao": recomendacao  # 🆕
            },
            
            "padroes": {
                "master": {
                    "padroes_encontrados": resultado_master.metadata.get('padroes_encontrados', 0),
                    "modo": resultado_master.metadata.get('modo', 'normal'),
                    "top_5": [num for num, _ in resultado_master.get_top_n(5)]
                },
                "estelar": {
                    "padroes_equivalentes": resultado_estelar.metadata.get('padroes_equivalentes', 0),
                    "tipos": resultado_estelar.metadata.get('tipos_equivalencia', {}),
                    "top_5": [num for num, _ in resultado_estelar.get_top_n(5)]
                },
                "chain": {
                    "cadeias_aprendidas": resultado_chain.metadata.get('total_cadeias_aprendidas', 0),
                    "inversoes": resultado_chain.metadata.get('inversoes_detectadas', 0),
                    "compensacoes": resultado_chain.metadata.get('compensacoes_detectadas', 0),
                    "top_pares": resultado_chain.metadata.get('top_pares', [])[:5],
                    "top_5": [num for num, _ in resultado_chain.get_top_n(5)]
                },
                "temporal": {
                    "time_analyzed": resultado_temporal[1].get('time_analyzed', ''),
                    "interval_minutes": resultado_temporal[1].get('interval_minutes', 0),
                    "interval_end": resultado_temporal[1].get('interval_end', ''),
                    "days_analyzed": resultado_temporal[1].get('days_analyzed', 0),
                    "total_occurrences": resultado_temporal[1].get('total_occurrences', 0),
                    "days_with_data": resultado_temporal[1].get('days_with_data', 0),
                    "candidates_found": resultado_temporal[1].get('candidates_found', 0),
                    "top_5_historical": resultado_temporal[1].get('top_5_historical', [])[:5]
                },
                "comportamentos_imediatos": {  # 🆕
                    "alternancia_tripla": resultado_comportamentos.metadata.get('alternancia_tripla_detectada', False),
                    "repeticoes_duplas": resultado_comportamentos.metadata.get('repeticoes_duplas', 0),
                    "cavalos_incompletos": resultado_comportamentos.metadata.get('cavalos_incompletos', []),
                    "crescentes_detectadas": resultado_comportamentos.metadata.get('crescentes_detectadas', []),
                    "substituicoes": resultado_comportamentos.metadata.get('substituicoes_detectadas', []),
                    "confianca": resultado_comportamentos.metadata.get('nivel_confianca', 0),
                    "top_5": [num for num, _ in resultado_comportamentos.get_top_n(5)]
                }
            },
            
            "validacao_ancoras": info_validacao,  # 🆕
            
            "configuracao": {
                "pesos": {
                    "master": round(w_master, 3),
                    "estelar": round(w_estelar, 3),
                    "chain": round(w_chain, 3),
                    "temporal": round(w_temporal, 3),
                    "comportamentos": round(w_comportamentos, 3)
                },
                "pesos_dinamicos": usar_pesos_dinamicos,
                "validacao_ancoras": validar_ancoras,
                "confianca_minima": min_confianca,
                "quantidade_solicitada": quantidade,
                "protecoes_habilitadas": incluir_protecoes,
                "historico_analisado": len(numeros)
            }
        }
        
        logger.info(
            f"Sugestão gerada: {len(candidatos_top)} principais + "
            f"{len(protecoes_result['protecoes'])} proteções | "
            f"Força: {forca_sinal['classificacao']} ({forca_sinal['valor']}/100) | "
            f"Comportamento: {comportamento_dominante['tipo']}"
        )
        
        # Retorna HTML ou JSON baseado no Accept header
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return templates.TemplateResponse(
                "sugestao.html",
                {
                    "request": request,
                    "slug": roulette_id,
                    "dados": resposta,
                }
            )
        
        return JSONResponse(content=resposta)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar sugestão: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar sugestão: {str(e)}"
        )


# Rotas adicionais para debugging e análise

@router.get("/debug/comportamentos/{roulette_id}")
async def debug_comportamentos(
    request: Request,
    roulette_id: str,
    janela: int = Query(10, ge=5, le=20, description="Janela de análise")
):
    """
    🆕 Debug dos comportamentos imediatos detectados
    
    Returns:
        Análise detalhada dos comportamentos nos últimos N números
    """
    try:
        numeros = await _get_historico_interno(request, roulette_id, limit=100)
        
        comportamentos = ComportamentosImediatos()
        resultado = comportamentos.analyze_debug(numeros[:janela])
        
        return JSONResponse(content={
            "roulette_id": roulette_id,
            "janela_analisada": janela,
            "numeros": numeros[:janela],
            "comportamentos_detectados": resultado
        })
        
    except Exception as e:
        logger.error(f"Erro no debug de comportamentos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/debug/ancoras/{roulette_id}")
async def debug_ancoras(
    request: Request,
    roulette_id: str
):
    """
    🆕 Debug da validação por múltiplas âncoras
    
    Returns:
        Análise detalhada das âncoras e confluências
    """
    try:
        numeros = await _get_historico_interno(request, roulette_id, limit=200)
        
        validador = ValidadorMultiplasAncoras()
        estrutura = validador.identificar_estrutura_detalhada(numeros[:30])
        
        return JSONResponse(content={
            "roulette_id": roulette_id,
            "estrutura_narrativa": estrutura,
            "numeros_analisados": numeros[:30]
        })
        
    except Exception as e:
        logger.error(f"Erro no debug de âncoras: {e}")
        raise HTTPException(status_code=500, detail=str(e))