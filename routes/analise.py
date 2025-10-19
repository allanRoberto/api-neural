"""
Rota para análises detalhadas (Master, Estelar, Chain separados)
CADA ROTA RETORNA APENAS UM PADRÃO ESPECÍFICO
"""

from fastapi import APIRouter, Request, HTTPException, Query
from typing import Dict
from datetime import datetime

# Importar padrões quando implementados
from patterns.master import MasterPattern
# from patterns.estelar import EstelarPattern  # TODO
# from patterns.chain import ChainPattern      # TODO

router = APIRouter()

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


@router.get("/{roulette_id}/master")
async def analise_master(
    request: Request,
    roulette_id: str,
    janela_min: int = Query(default=2, ge=2, le=5),
    janela_max: int = Query(default=4, ge=2, le=5),
    min_support: int = Query(default=2, ge=1, le=5)
) -> Dict:
    """
    Análise usando APENAS padrão MASTER
    
    Args:
        roulette_id: ID da roleta
        janela_min: Tamanho mínimo da janela
        janela_max: Tamanho máximo da janela
        min_support: Mínimo de ocorrências
    
    Returns:
        Análise detalhada do padrão MASTER
    """
    try:
        # Buscar histórico
        numeros = await _get_historico_interno(request, roulette_id)
        
        # Criar instância do MASTER
        master = MasterPattern(config={
            'janela_min': janela_min,
            'janela_max': janela_max,
            'decay_factor': 0.95,
            'min_support': min_support
        })
        
        # Analisar
        resultado = master.analyze(numeros)
        top_candidatos = resultado.get_top_n(18)  # Top 18
        
        return {
            "roulette_id": roulette_id,
            "timestamp": datetime.now().isoformat(),
            "pattern": "MASTER",
            "status": "success",
            "candidatos": [
                {
                    "numero": num,
                    "score": score,
                    "posicao": idx + 1
                }
                for idx, (num, score) in enumerate(top_candidatos)
            ],
            "metadata": {
                "historico_size": len(numeros),
                "ultimos_10": numeros[:10],
                "padroes_encontrados": resultado.metadata['padroes_encontrados'],
                "janelas_analisadas": resultado.metadata['janelas_analisadas'],
                "relacoes_detectadas": resultado.metadata['relacoes_detectadas']
            },
            "config": {
                "janela_min": janela_min,
                "janela_max": janela_max,
                "min_support": min_support,
                "decay_factor": 0.95
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro na análise MASTER: {str(e)}"
        )



@router.get("/{roulette_id}/estelar")
async def analise_estelar(
    request: Request,
    roulette_id: str
) -> Dict:
    """
    Análise usando APENAS padrão ESTELAR
    
    TODO: Implementar classe EstelarPattern
    """
    try:
        numeros = await _get_historico_interno(request, roulette_id)
        
        return {
            "roulette_id": roulette_id,
            "timestamp": datetime.now().isoformat(),
            "pattern": "ESTELAR",
            "status": "not_implemented",
            "message": "Padrão ESTELAR será implementado",
            "historico_size": len(numeros),
            "ultimos_10": numeros[:10]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{roulette_id}/chain")
async def analise_chain(
    request: Request,
    roulette_id: str,
    quantidade: int = Query(default=6, ge=1, le=18, description="Quantidade de sugestões"),
    min_support: int = Query(default=2, ge=1, le=5, description="Mínimo de ocorrências"),
    decay: float = Query(default=0.95, ge=0.85, le=0.99, description="Decaimento temporal"),
    miss_window: int = Query(default=30, ge=10, le=50, description="Janela para faltantes")
):
    """
    Análise usando APENAS o padrão CHAIN (fluxo contextual)
    
    - **roulette_id**: ID da roleta
    - **quantidade**: Número de sugestões (1-18)
    - **min_support**: Mínimo de ocorrências para considerar cadeia (1-5)
    - **decay**: Decaimento temporal - maior = valoriza recente (0.85-0.99)
    - **miss_window**: Janela para identificar faltantes (10-50)
    
    Returns:
        JSON com candidatos e metadados do padrão CHAIN
    """
    try:
        db = request.app.state.db
        
        # Busca histórico
        numeros = await get_historico_from_db(db, roulette_id, limit=200)
        
        if not numeros or len(numeros) < min_support:
            raise HTTPException(
                status_code=404,
                detail=f"Histórico insuficiente para {roulette_id}"
            )
        
        # Cria instância com parâmetros customizados
        chain = ChainAnalyzer(
            min_chain_support=min_support,
            chain_decay=decay,
            recent_window_miss=miss_window
        )
        
        resultado = chain.analyze(numeros, limit=quantidade)
        
        return {
            "roulette_id": roulette_id,
            "padrao": "CHAIN",
            "descricao": "Análise contextual de fluxo comportamental (cadeias dinâmicas e faltantes)",
            "total_candidatos": len(resultado.candidatos),
            "candidatos": [
                {
                    "numero": c.numero,
                    "score": c.score,
                    "confianca": c.confianca,
                    "evidencias": [
                        {
                            "tipo": e.tipo,
                            "descricao": e.descricao,
                            "peso": e.peso,
                            "detalhes": e.detalhes
                        }
                        for e in c.evidencias[:3]
                    ]
                }
                for c in resultado.candidatos
            ],
            "metadados": resultado.metadados
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro na análise CHAIN: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar análise CHAIN: {str(e)}"
        )


@router.get("/{roulette_id}/completa")
async def analise_completa(
    request: Request,
    roulette_id: str,
    quantidade: int = Query(default=6, ge=1, le=18, description="Quantidade de sugestões por padrão")
):
    """
    Análise COMPLETA - retorna resultados de TODOS os padrões separadamente
    
    NÃO faz ensemble, apenas executa cada padrão individualmente.
    
    - **roulette_id**: ID da roleta
    - **quantidade**: Número de sugestões de cada padrão
    
    Returns:
        JSON com resultados de Master, Estelar e Chain separados
    """
    try:
        db = request.app.state.db
        
        # Busca histórico
        numeros = await get_historico_from_db(db, roulette_id, limit=200)
        
        if not numeros or len(numeros) < 10:
            raise HTTPException(
                status_code=404,
                detail=f"Histórico insuficiente para {roulette_id}"
            )
        
        # Executa cada padrão
        master = get_master_analyzer()
        estelar = get_estelar_analyzer()
        chain = get_chain_analyzer()
        
        resultado_master = master.analyze(numeros, limit=quantidade)
        resultado_estelar = estelar.analyze(numeros, limit=quantidade)
        resultado_chain = chain.analyze(numeros, limit=quantidade)
        
        return {
            "roulette_id": roulette_id,
            "tipo": "analise_completa",
            "descricao": "Resultados de todos os padrões executados separadamente",
            "total_numeros_analisados": len(numeros),
            "padroes": {
                "master": {
                    "total_candidatos": len(resultado_master.candidatos),
                    "candidatos": [
                        {
                            "numero": c.numero,
                            "score": c.score,
                            "confianca": c.confianca
                        }
                        for c in resultado_master.candidatos
                    ],
                    "top_3_detalhado": [
                        {
                            "numero": c.numero,
                            "score": c.score,
                            "evidencias": [e.descricao for e in c.evidencias[:2]]
                        }
                        for c in resultado_master.candidatos[:3]
                    ]
                },
                "estelar": {
                    "total_candidatos": len(resultado_estelar.candidatos),
                    "candidatos": [
                        {
                            "numero": c.numero,
                            "score": c.score,
                            "confianca": c.confianca
                        }
                        for c in resultado_estelar.candidatos
                    ],
                    "top_3_detalhado": [
                        {
                            "numero": c.numero,
                            "score": c.score,
                            "evidencias": [e.descricao for e in c.evidencias[:2]]
                        }
                        for c in resultado_estelar.candidatos[:3]
                    ]
                },
                "chain": {
                    "total_candidatos": len(resultado_chain.candidatos),
                    "candidatos": [
                        {
                            "numero": c.numero,
                            "score": c.score,
                            "confianca": c.confianca
                        }
                        for c in resultado_chain.candidatos
                    ],
                    "top_3_detalhado": [
                        {
                            "numero": c.numero,
                            "score": c.score,
                            "evidencias": [e.descricao for e in c.evidencias[:2]]
                        }
                        for c in resultado_chain.candidatos[:3]
                    ],
                    "cadeias_aprendidas": resultado_chain.metadados.get('total_cadeias_aprendidas', 0),
                    "inversoes": resultado_chain.metadados.get('inversoes_detectadas', 0),
                    "compensacoes": resultado_chain.metadados.get('compensacoes_detectadas', 0)
                }
            },
            "sobreposicao": _calcular_sobreposicao(
                [c.numero for c in resultado_master.candidatos[:quantidade]],
                [c.numero for c in resultado_estelar.candidatos[:quantidade]],
                [c.numero for c in resultado_chain.candidatos[:quantidade]]
            )
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro na análise completa: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar análise completa: {str(e)}"
        )


def _calcular_sobreposicao(master_nums: list, estelar_nums: list, chain_nums: list) -> dict:
    """Calcula sobreposição entre os padrões"""
    set_master = set(master_nums)
    set_estelar = set(estelar_nums)
    set_chain = set(chain_nums)
    
    # Consenso triplo (aparecem nos 3 padrões)
    consenso_triplo = set_master & set_estelar & set_chain
    
    # Consenso duplo
    master_estelar = set_master & set_estelar - consenso_triplo
    master_chain = set_master & set_chain - consenso_triplo
    estelar_chain = set_estelar & set_chain - consenso_triplo
    
    return {
        "consenso_triplo": list(consenso_triplo),
        "consenso_duplo": {
            "master_estelar": list(master_estelar),
            "master_chain": list(master_chain),
            "estelar_chain": list(estelar_chain)
        },
        "unicos": {
            "master": list(set_master - set_estelar - set_chain),
            "estelar": list(set_estelar - set_master - set_chain),
            "chain": list(set_chain - set_master - set_estelar)
        }
    }