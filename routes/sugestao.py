"""
routes/sugestao.py

Rota para sugestões com Ensemble MASTER + ESTELAR + CHAIN
Inclui proteções dinâmicas (espelhos, vizinhos, zero)
"""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Dict, Set
from collections import defaultdict
import logging

from patterns.master import MasterPattern
from patterns.estelar import EstelarPattern
from patterns.chain import ChainAnalyzer
from utils.constants import ESPELHOS
from utils.helpers import get_vizinhos
from fastapi.responses import  JSONResponse
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

def calcular_ensemble(
    resultado_master,
    resultado_estelar,
    resultado_chain,
    w_master: float = 0.35,
    w_estelar: float = 0.35,
    w_chain: float = 0.30
) -> Dict[int, float]:
    """
    Combina scores dos 3 padrões com pesos configuráveis
    
    Args:
        resultado_master: PatternResult do MASTER
        resultado_estelar: PatternResult do ESTELAR
        resultado_chain: PatternResult do CHAIN
        w_master: Peso do MASTER (0-1)
        w_estelar: Peso do ESTELAR (0-1)
        w_chain: Peso do CHAIN (0-1)
    
    Returns:
        Dict {numero: score_combinado} normalizado
    """
    # Ajuste dinâmico de pesos
    padroes_chain = resultado_chain.metadata.get('total_cadeias_aprendidas', 0)
    
    if padroes_chain > 1000:
        # CHAIN encontrou muitos padrões, aumenta peso
        w_chain = 0.40
        w_master = 0.30
        w_estelar = 0.30
        logger.info(f"Ajuste dinâmico: CHAIN com {padroes_chain} cadeias, peso aumentado para 40%")
    
    # Normaliza pesos
    total_peso = w_master + w_estelar + w_chain
    w_master /= total_peso
    w_estelar /= total_peso
    w_chain /= total_peso
    
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
    
    # Normaliza resultado final
    if scores_combinados:
        max_score = max(scores_combinados.values())
        if max_score > 0:
            scores_combinados = {
                num: score / max_score
                for num, score in scores_combinados.items()
            }
    
    return dict(scores_combinados)


def aplicar_protecoes(
    candidatos_base: List[int],
    historico: List[int],
    incluir_zero: bool = True,
    incluir_espelhos: bool = True,
    incluir_vizinhos: bool = True,
    max_protecoes: int = 6
) -> Dict[str, List[int]]:
    """
    Adiciona proteções aos candidatos base
    
    Args:
        candidatos_base: Lista de números principais
        historico: Histórico completo
        incluir_zero: Incluir o número 0
        incluir_espelhos: Incluir espelhos dos candidatos
        incluir_vizinhos: Incluir vizinhos dos candidatos
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
    
    # 4. COMPLETAR RUAS (se 2 de 3 presentes)
    ruas = [
        [1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12],
        [13, 14, 15], [16, 17, 18], [19, 20, 21], [22, 23, 24],
        [25, 26, 27], [28, 29, 30], [31, 32, 33], [34, 35, 36]
    ]
    
    for rua in ruas:
        presentes = [n for n in rua if n in candidatos_base]
        if len(presentes) == 2:
            # 2 de 3 presentes, adiciona o faltante
            faltante = [n for n in rua if n not in candidatos_base][0]
            if faltante not in protecoes:
                protecoes.add(faltante)
    
    # 5. FAMÍLIA DE DEZENAS (se relevante)
    # Ex: se tem 2, 12, 22 → adiciona 32
    for terminal in range(10):
        familia = [n for n in [terminal, 10+terminal, 20+terminal, 30+terminal] 
                   if 0 <= n <= 36]
        presentes = [n for n in familia if n in candidatos_base]
        
        if len(presentes) >= 2:
            for num in familia:
                if num not in candidatos_base and num not in protecoes:
                    protecoes.add(num)
                    break  # Só adiciona 1 da família
    
    # Limita proteções ao máximo
    protecoes_lista = sorted(list(protecoes))[:max_protecoes]
    
    return {
        'candidatos': candidatos_base,
        'protecoes': protecoes_lista,
        'total_protegido': len(candidatos_base) + len(protecoes_lista)
    }


def identificar_faltantes(candidatos: List[int], historico: List[int], window: int = 30) -> List[int]:
    """
    Identifica faltantes (não apareceram recentemente)
    
    Args:
        candidatos: Lista de candidatos
        historico: Histórico completo
        window: Janela de análise
    
    Returns:
        Lista de números faltantes
    """
    recent_set = set(historico[:window])
    return [num for num in candidatos if num not in recent_set]


def calcular_consenso(
    candidatos: List[int],
    resultado_master,
    resultado_estelar,
    resultado_chain
) -> Dict:
    """
    Calcula consenso entre os padrões
    
    Returns:
        Dict com análise de consenso
    """
    set_candidatos = set(candidatos)
    set_master = set(resultado_master.scores.keys())
    set_estelar = set(resultado_estelar.scores.keys())
    set_chain = set(resultado_chain.scores.keys())
    
    # Consenso total (3/3)
    consenso_total = set_candidatos & set_master & set_estelar & set_chain
    
    # Consenso duplo
    me = set_candidatos & set_master & set_estelar - consenso_total
    mc = set_candidatos & set_master & set_chain - consenso_total
    ec = set_candidatos & set_estelar & set_chain - consenso_total
    
    # Únicos
    so_master = set_candidatos & set_master - set_estelar - set_chain
    so_estelar = set_candidatos & set_estelar - set_master - set_chain
    so_chain = set_candidatos & set_chain - set_master - set_estelar
    
    return {
        'consenso_total': sorted(list(consenso_total)),
        'consenso_duplo': {
            'master_estelar': sorted(list(me)),
            'master_chain': sorted(list(mc)),
            'estelar_chain': sorted(list(ec))
        },
        'unicos': {
            'master': sorted(list(so_master)),
            'estelar': sorted(list(so_estelar)),
            'chain': sorted(list(so_chain))
        }
    }


@router.get("/{roulette_id}")
async def sugestao_ensemble(
    request: Request,
    roulette_id: str,
    quantidade: int = Query(default=6, ge=1, le=12, description="Quantidade de sugestões principais"),
    incluir_protecoes: bool = Query(default=True, description="Incluir proteções (espelhos, vizinhos)"),
    max_protecoes: int = Query(default=6, ge=0, le=10, description="Máximo de proteções adicionais"),
    w_master: float = Query(default=0.35, ge=0, le=1, description="Peso do MASTER"),
    w_estelar: float = Query(default=0.35, ge=0, le=1, description="Peso do ESTELAR"),
    w_chain: float = Query(default=0.30, ge=0, le=1, description="Peso do CHAIN"),
    incluir_zero: bool = Query(default=True, description="Sempre incluir zero nas proteções"),
    limite_historico: int = Query(default=2000, ge=100, le=5000, description="Quantidade de histórico")
):
    """
    Sugestão completa com Ensemble MASTER + ESTELAR + CHAIN
    
    ## Parâmetros:
    
    - **quantidade**: Número de sugestões principais (1-12)
    - **incluir_protecoes**: Adicionar proteções automáticas
    - **max_protecoes**: Máximo de números de proteção (0-10)
    - **w_master**: Peso do MASTER no ensemble (0-1)
    - **w_estelar**: Peso do ESTELAR no ensemble (0-1)
    - **w_chain**: Peso do CHAIN no ensemble (0-1)
    - **incluir_zero**: Incluir zero automaticamente
    - **limite_historico**: Quantidade de histórico a analisar
    
    ## Retorna:
    
    - Lista de sugestões principais
    - Proteções (se habilitado)
    - Análise de consenso
    - Faltantes identificados
    - Metadados dos 3 padrões
    """
    try:
        db = request.app.state.db
        
        # Busca histórico
        logger.info(f"Buscando histórico para {roulette_id} (limite: {limite_historico})")
        numeros = await _get_historico_interno(request, roulette_id)
        
        if not numeros or len(numeros) < 50:
            raise HTTPException(
                status_code=404,
                detail=f"Histórico insuficiente para {roulette_id} (mínimo: 50 números)"
            )
        
        logger.info(f"Histórico obtido: {len(numeros)} números")
        
        # Configurações dos padrões
        config_master = {
            "janela_min": 2,
            "janela_max": 3,
            "min_support": 1,
            "janelas_recentes": 15
        }
        
        config_estelar = {
            "estrutura_min": 2,
            "estrutura_max": 3,
            "min_support": 1
        }
        
        config_chain = {
            "min_chain_support": 2,
            "chain_decay": 0.95,
            "recent_window_miss": 30,
            "max_chain_length": 4
        }
        
        # Executa análises
        logger.info("Executando MASTER...")
        master = MasterPattern(config=config_master)
        resultado_master = master.analyze(numeros)
        
        logger.info("Executando ESTELAR...")
        estelar = EstelarPattern(config=config_estelar)
        resultado_estelar = estelar.analyze(numeros)
        
        logger.info("Executando CHAIN...")
        chain = ChainAnalyzer(config=config_chain)
        resultado_chain = chain.analyze(numeros)
        
        # Calcula ensemble
        logger.info("Calculando ensemble...")
        scores_ensemble = calcular_ensemble(
            resultado_master,
            resultado_estelar,
            resultado_chain,
            w_master=w_master,
            w_estelar=w_estelar,
            w_chain=w_chain
        )
        
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
        
        # Calcula consenso
        consenso = calcular_consenso(
            candidatos_top,
            resultado_master,
            resultado_estelar,
            resultado_chain
        )
        
        # Aplica proteções
        if incluir_protecoes:
            protecoes_result = aplicar_protecoes(
                candidatos_top,
                numeros,
                incluir_zero=incluir_zero,
                incluir_espelhos=True,
                incluir_vizinhos=True,
                max_protecoes=max_protecoes
            )
        else:
            protecoes_result = {
                'candidatos': candidatos_top,
                'protecoes': [],
                'total_protegido': len(candidatos_top)
            }
        
        # Constrói resposta
        resposta = {
            "roulette_id": roulette_id,
            "timestamp": numeros[0] if numeros else None,
            "sugestoes": {
                "principais": [
                    {
                        "numero": num,
                        "score": round(scores_ensemble[num], 6),
                        "ranking": i + 1,
                        "faltante": num in faltantes,
                        "consenso": _get_consenso_nivel(num, consenso)
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
                "ultimo_numero": numeros[0],
                "ultimos_10": numeros[:10]
            },
            "padroes": {
                "master": {
                    "padroes_encontrados": resultado_master.metadata.get('padroes_encontrados', 0),
                    "modo": resultado_master.metadata.get('modo', 'normal'),
                    "top_3": [num for num, _ in resultado_master.get_top_n(3)]
                },
                "estelar": {
                    "padroes_equivalentes": resultado_estelar.metadata.get('padroes_equivalentes', 0),
                    "tipos": resultado_estelar.metadata.get('tipos_equivalencia', {}),
                    "top_3": [num for num, _ in resultado_estelar.get_top_n(3)]
                },
                "chain": {
                    "cadeias_aprendidas": resultado_chain.metadata.get('total_cadeias_aprendidas', 0),
                    "inversoes": resultado_chain.metadata.get('inversoes_detectadas', 0),
                    "compensacoes": resultado_chain.metadata.get('compensacoes_detectadas', 0),
                    "top_pares": resultado_chain.metadata.get('top_pares', [])[:5],
                    "top_3": [num for num, _ in resultado_chain.get_top_n(3)]
                }
            },
            "configuracao": {
                "pesos": {
                    "master": w_master,
                    "estelar": w_estelar,
                    "chain": w_chain
                },
                "quantidade_solicitada": quantidade,
                "protecoes_habilitadas": incluir_protecoes,
                "historico_analisado": len(numeros)
            }
        }
        
        logger.info(
            f"Sugestão gerada: {len(candidatos_top)} principais + "
            f"{len(protecoes_result['protecoes'])} proteções"
        )
        

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

        return JSONResponse(content={resposta})

        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar sugestão: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar sugestão: {str(e)}"
        )


def _get_consenso_nivel(numero: int, consenso: Dict) -> str:
    """Retorna nível de consenso de um número"""
    if numero in consenso['consenso_total']:
        return "total_3/3"
    
    for tipo, nums in consenso['consenso_duplo'].items():
        if numero in nums:
            return f"duplo_{tipo}"
    
    for tipo, nums in consenso['unicos'].items():
        if numero in nums:
            return f"unico_{tipo}"
    
    return "ensemble"


def _get_tipo_protecao(numero: int, candidatos: List[int], historico: List[int]) -> str:
    """Identifica tipo de proteção"""
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