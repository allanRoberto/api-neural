"""
Rota para análises detalhadas (Master, Estelar, Chain separados)
CADA ROTA RETORNA APENAS UM PADRÃO ESPECÍFICO
"""

from fastapi import APIRouter, Request, HTTPException, Query
from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator
from datetime import datetime, timedelta
from fastapi.templating import Jinja2Templates


# Importar padrões quando implementados
from patterns.master import PatternMaster
from patterns.estelar import PatternEstelar  

templates = Jinja2Templates(directory="templates")

# Ordem dos números na roleta física (sentido horário)
ROULETTE_WHEEL_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11,
    30, 8, 23, 10, 5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18,
    29, 7, 28, 12, 35, 3, 26
]

# Modelos Pydantic
class HeatmapRequest(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="Hora base (0-23)")
    minute: int = Field(..., ge=0, le=59, description="Minuto base (0-59)")
    days: int = Field(..., ge=1, le=365, description="Quantos dias buscar (1-365)")
    neighbors: int = Field(..., ge=0, le=5, description="Quantos vizinhos pontuar de cada lado (0-5)")
    minute_range: int = Field(..., ge=0, le=10, description="Intervalo de minutos (0-10)")
    direction: str = Field(..., description="Direção: 'both', 'forward', 'backward'")
    
    class Config:
        json_schema_extra = {
            "example": {
                "hour": 17,
                "minute": 40,
                "days": 30,
                "neighbors": 2,
                "minute_range": 2,
                "direction": "both"
            }
        }


class HeatmapResponse(BaseModel):
    success: bool
    scores: Dict[int, float]
    metadata: dict


# Modelos Pydantic para validação
class AnalyzeRequest(BaseModel):
    hour: int = Field(..., ge=0, le=23, description="Hora (0-23)")
    minute: int = Field(..., ge=0, le=59, description="Minuto (0-59)")
    days: int = Field(..., ge=1, le=365, description="Últimos X dias (1-365)")
    nextNumbers: int = Field(..., ge=1, le=20, description="Próximos X números (1-20)")

    class Config:
        json_schema_extra = {
            "example": {
                "hour": 11,
                "minute": 13,
                "days": 30,
                "nextNumbers": 5
            }
        }


class ResultItem(BaseModel):
    date: str
    time: str
    drawnNumber: int
    nextNumbers: List[int]
    timestamp: str


class AnalyzeResponse(BaseModel):
    success: bool
    results: List[ResultItem]
    metadata: dict


class TopNumber(BaseModel):
    number: int
    count: int
    percentage: str


class StatsResponse(BaseModel):
    success: bool
    totalRecords: int
    topNumbers: List[TopNumber]


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    database_connected: bool


router = APIRouter()


def get_neighbor_numbers(number: int, distance: int, wheel_order: List[int]) -> List[int]:
    """
    Retorna os vizinhos de um número na roleta física
    
    Args:
        number: Número na roleta (0-36)
        distance: Quantos vizinhos de distância (1=imediato, 2=segundo, etc)
        wheel_order: Ordem dos números na roleta
    
    Returns:
        Lista com [vizinho_esquerdo, vizinho_direito]
    """
    try:
        index = wheel_order.index(number)
        
        # Vizinho à esquerda (anti-horário)
        left_index = (index - distance) % len(wheel_order)
        left_neighbor = wheel_order[left_index]
        
        # Vizinho à direita (horário)
        right_index = (index + distance) % len(wheel_order)
        right_neighbor = wheel_order[right_index]
        
        return [left_neighbor, right_neighbor]
    except ValueError:
        return []


def calculate_minute_range(base_minute: int, minute_range: int, direction: str) -> List[int]:
    """
    Calcula a lista de minutos a buscar
    
    Args:
        base_minute: Minuto base (ex: 40)
        minute_range: Intervalo (ex: 2)
        direction: 'both', 'forward', 'backward'
    
    Returns:
        Lista de minutos (ex: [38, 39, 40, 41, 42])
    """
    minutes = [base_minute]
    
    if direction in ['both', 'backward']:
        # Adicionar minutos anteriores
        for i in range(1, minute_range + 1):
            min_val = base_minute - i
            if min_val >= 0:
                minutes.insert(0, min_val)
    
    if direction in ['both', 'forward']:
        # Adicionar minutos posteriores
        for i in range(1, minute_range + 1):
            min_val = base_minute + i
            if min_val <= 59:
                minutes.append(min_val)
    
    return minutes

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


@router.get("/{roulette_id}/heatmap")
async def heatmap_html(request: Request, roulette_id: str):
    """
    Renderiza a interface HTML do mapa de calor
    """
    return templates.TemplateResponse(
        "heatmap.html",
        {
            "request": request,
            "roulette_id": roulette_id,
            "title": "Mapa de Calor - Roleta",
            "header_title": "🔥 Mapa de Calor da Roleta",
            "header_subtitle": "Análise de Regiões Quentes por Horário",
            "default_hour": 17,
            "default_minute": 40,
            "default_days": 30,
            "default_neighbors": 2,
            "default_minute_range": 2,
            "default_direction": "both"
        }
    )


@router.post("/{roulette_id}/heatmap", response_model=HeatmapResponse)
async def analyze_heatmap(request: Request, data: HeatmapRequest, roulette_id: str):
    """
    Endpoint principal de análise do mapa de calor
    
    Busca números sorteados em horários específicos e calcula scores
    incluindo pontuação de vizinhos na roleta física
    """
    try:
        # Acessar database
        db = request.app.state.db
        settings = request.app.state.settings
        collection = db[settings.MONGODB_COLLECTION]
        
        # Validar direção
        if data.direction not in ['both', 'forward', 'backward']:
            raise HTTPException(
                status_code=400,
                detail="Direção deve ser 'both', 'forward' ou 'backward'"
            )
        
        # Calcular período de busca
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=data.days)
        
        # Calcular lista de minutos a buscar
        minutes_to_search = calculate_minute_range(
            data.minute,
            data.minute_range,
            data.direction
        )
        
        print(f"🔍 Buscando registros de {start_date} até {end_date}")
        print(f"⏰ Horário base: {data.hour:02d}:{data.minute:02d}")
        print(f"📍 Minutos a buscar: {minutes_to_search}")
        print(f"🎯 Vizinhos: {data.neighbors} de cada lado")
        
        # Buscar registros usando agregação MongoDB
        pipeline = [
            {
                '$match': {
                    'roulette_name': roulette_id,
                    'timestamp': {
                        '$gte': start_date,
                        '$lte': end_date
                    }
                }
            },
            {
                '$addFields': {
                    'hour': {'$hour': '$timestamp'},
                    'minute': {'$minute': '$timestamp'}
                }
            },
            {
                '$match': {
                    'hour': data.hour,
                    'minute': {'$in': minutes_to_search}
                }
            },
            {
                '$sort': {'timestamp': -1}
            }
        ]
        
        records = await collection.aggregate(pipeline).to_list(length=None)
        
        print(f"📊 Registros encontrados: {len(records)}")
        
        if not records:
            # Retornar scores zerados
            return HeatmapResponse(
                success=True,
                scores={i: 0.0 for i in range(37)},
                metadata={
                    'total_records': 0,
                    'base_hour': data.hour,
                    'base_minute': data.minute,
                    'minutes_searched': minutes_to_search,
                    'days': data.days,
                    'neighbors': data.neighbors,
                    'direction': data.direction,
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'message': 'Nenhum registro encontrado'
                }
            )
        
        # Inicializar scores (0-36)
        scores = {i: 0.0 for i in range(37)}
        
        # Processar cada registro
        for record in records:
            number = record.get('value')
            
            if number is None or not (0 <= number <= 36):
                continue
            
            # Score principal (peso 1.0)
            scores[number] += 1.0
            
            # Pontuar vizinhos (se configurado)
            if data.neighbors > 0:
                for distance in range(1, data.neighbors + 1):
                    # Peso decrescente por distância
                    # 1º vizinho = 0.5, 2º = 0.25, 3º = 0.125, etc.
                    neighbor_weight = 0.5 / (1.3 ** distance)
                    
                    neighbors = get_neighbor_numbers(
                        number,
                        distance,
                        ROULETTE_WHEEL_ORDER
                    )
                    
                    for neighbor in neighbors:
                        scores[neighbor] += neighbor_weight
        
        # Arredondar scores para 2 casas decimais
        scores = {k: round(v, 2) for k, v in scores.items()}
        
        # Calcular estatísticas
        max_score = max(scores.values()) if scores else 0
        min_score = min(scores.values()) if scores else 0
        total_score = sum(scores.values())
        avg_score = total_score / 37 if total_score > 0 else 0
        
        # Encontrar top 5 números mais quentes
        top_numbers = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return HeatmapResponse(
            success=True,
            scores=scores,
            metadata={
                'total_records': len(records),
                'base_hour': data.hour,
                'base_minute': data.minute,
                'minutes_searched': minutes_to_search,
                'days': data.days,
                'neighbors': data.neighbors,
                'direction': data.direction,
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'max_score': round(max_score, 2),
                'min_score': round(min_score, 2),
                'avg_score': round(avg_score, 2),
                'total_score': round(total_score, 2),
                'top_5_numbers': [
                    {'number': num, 'score': score}
                    for num, score in top_numbers
                ]
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Erro na análise do mapa de calor: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar mapa de calor: {str(e)}"
        )





@router.get("/{roulette_id}/temporal")
async def analyze_roleta_html(request:Request, roulette_id) :
    """
    Renderiza a interface HTML usando Jinja2Templates
    
    Você pode passar variáveis para customizar a página:
    - title: Título da página
    - header_title: Título do cabeçalho
    - header_subtitle: Subtítulo
    - default_hour, default_minute, default_days, default_next_numbers: Valores padrão
    """
    return templates.TemplateResponse(
        "analize.html",
        {
            "request": request,
            "title": "Analisador de Roleta",
            "header_title": "Analisador de Roleta",
            "header_subtitle": "Análise Personalizada",
            "default_hour": 11,
            "default_minute": 13,
            "default_days": 30,
            "default_next_numbers": 5
        }
    )

@router.post("/{roulette_id}/temporal", response_model=AnalyzeResponse)
async def analyze_roleta(request: Request, data: AnalyzeRequest, roulette_id):
    """
    Endpoint principal de análise
    
    Busca números sorteados em horário específico e retorna os próximos números
    """
    try:
        
        print(data.days)


        db = request.app.state.db
        settings = request.app.state.settings
        collection = db[settings.MONGODB_COLLECTION]
        # Calcular período
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=data.days)
        
        print(f"🔍 Buscando registros de {start_date} até {end_date}")
        print(f"⏰ Horário: {data.hour:02d}:{data.minute:02d}")
        
        # Buscar todos os registros no período usando agregação
        pipeline = [
            {
                '$match': {
                    'roulette_name': roulette_id,
                    'timestamp': {
                        '$gte': start_date,
                        '$lte': end_date
                    }
                }
            },
            {
                '$addFields': {
                    'hour': {'$hour': '$timestamp'},
                    'minute': {'$minute': '$timestamp'}
                }
            },
            {
                '$match': {
                    'hour': data.hour,
                    'minute': data.minute
                }
            },
            {
                '$sort': {'timestamp': 1}
            }
        ]
        
        records_at_time = await collection.aggregate(pipeline).to_list(length=None)

        
        print(f"📊 Registros encontrados às {data.hour:02d}:{data.minute:02d}: {len(records_at_time)}")
        
        if not records_at_time:
            return AnalyzeResponse(
                success=True,
                results=[],
                metadata={
                    'totalRecords': 0,
                    'period': f'{data.days} dias',
                    'time': f'{data.hour:02d}:{data.minute:02d}',
                    'nextNumbers': data.nextNumbers,
                    'startDate': start_date.strftime('%Y-%m-%d'),
                    'endDate': end_date.strftime('%Y-%m-%d'),
                    'message': 'Nenhum registro encontrado para os parâmetros especificados'
                }
            )
        
        # Para cada registro, buscar os próximos números
        results = []
        
        for record in records_at_time:
            timestamp = record['timestamp']
            
            # Buscar próximos N números
            next_records = await collection.find({
                'roulette_name': roulette_id,
                'timestamp': {'$gt': timestamp}
            }).sort('timestamp', 1).limit(data.nextNumbers).to_list(length=data.nextNumbers)
            
            # Formatar resultado
            results.append(ResultItem(
                date=timestamp.strftime('%Y-%m-%d'),
                time=timestamp.strftime('%H:%M:%S'),
                drawnNumber=record['value'],
                nextNumbers=[r['value'] for r in next_records],
                timestamp=timestamp.isoformat()
            ))
        
        # Ordenar por data decrescente
        results.sort(key=lambda x: x.timestamp, reverse=True)
        
        return AnalyzeResponse(
            success=True,
            results=results,
            metadata={
                'totalRecords': len(results),
                'period': f'{data.days} dias',
                'time': f'{data.hour:02d}:{data.minute:02d}',
                'nextNumbers': data.nextNumbers,
                'startDate': start_date.strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d')
            }
        )
    
    except Exception as e:
        print(f"❌ Erro na análise: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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

""" 
@router.get("/{roulette_id}/chain")
async def analise_chain(
    request: Request,
    roulette_id: str,
    quantidade: int = Query(default=6, ge=1, le=18, description="Quantidade de sugestões"),
    min_support: int = Query(default=2, ge=1, le=5, description="Mínimo de ocorrências"),
    decay: float = Query(default=0.95, ge=0.85, le=0.99, description="Decaimento temporal"),
    miss_window: int = Query(default=30, ge=10, le=50, description="Janela para faltantes")
):
    
    Análise usando APENAS o padrão CHAIN (fluxo contextual)
    
    - **roulette_id**: ID da roleta
    - **quantidade**: Número de sugestões (1-18)
    - **min_support**: Mínimo de ocorrências para considerar cadeia (1-5)
    - **decay**: Decaimento temporal - maior = valoriza recente (0.85-0.99)
    - **miss_window**: Janela para identificar faltantes (10-50)
    
    Returns:
        JSON com candidatos e metadados do padrão CHAIN
    
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
    
    Análise COMPLETA - retorna resultados de TODOS os padrões separadamente
    
    NÃO faz ensemble, apenas executa cada padrão individualmente.
    
    - **roulette_id**: ID da roleta
    - **quantidade**: Número de sugestões de cada padrão
    
    Returns:
        JSON com resultados de Master, Estelar e Chain separados
    
    try:
        db = request.app.state.db
        
        # Busca histórico
        numeros = await _get_historico_interno(db, roulette_id, limit=200)
        
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

 """
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