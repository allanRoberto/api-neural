# ========== routes/historico.py ==========
"""
Rota para buscar histórico de números
ADAPTADO: usa 'value' ao invés de 'number'
"""

from fastapi import APIRouter, Request, HTTPException, Query
from typing import List, Dict
from datetime import datetime

router = APIRouter()


@router.get("/{roulette_id}")
async def get_historico(
    request: Request,
    roulette_id: str,
    limit: int = Query(default=500, ge=1, le=1000, description="Quantidade de números")
) -> Dict:
    """
    Busca histórico de números de uma roleta
    
    Args:
        roulette_id: ID da roleta (ex: "pragmatic-turkish-mega-roulette")
        limit: Quantidade de números (máx 1000)
    
    Returns:
        Histórico de números ordenados do mais recente para o mais antigo
    """
    try:
        db = request.app.state.db
        settings = request.app.state.settings
        
        # Buscar do MongoDB
        collection = db[settings.MONGODB_COLLECTION]
        
        cursor = collection.find(
            {"roulette_id": roulette_id}
        ).sort("timestamp", -1).limit(limit)
        
        documents = await cursor.to_list(length=limit)
        
        # Extrair apenas os números (campo 'value')
        numeros = [doc.get("value", 0) for doc in documents]
        
        return {
            "roulette_id": roulette_id,
            "timestamp": datetime.now().isoformat(),
            "total": len(numeros),
            "numeros": numeros  # Lista de 0-36
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar histórico: {str(e)}"
        )


@router.get("/{roulette_id}/detailed")
async def get_historico_detailed(
    request: Request,
    roulette_id: str,
    limit: int = Query(default=100, ge=1, le=500)
) -> Dict:
    """
    Busca histórico detalhado (com timestamp, roulette_name, etc)
    """
    try:
        db = request.app.state.db
        settings = request.app.state.settings
        
        collection = db[settings.MONGODB_COLLECTION]
        
        cursor = collection.find(
            {"roulette_id": roulette_id}
        ).sort("timestamp", -1).limit(limit)
        
        documents = await cursor.to_list(length=limit)
        
        # Converter ObjectId para string
        for doc in documents:
            doc["_id"] = str(doc["_id"])
        
        return {
            "roulette_id": roulette_id,
            "timestamp": datetime.now().isoformat(),
            "total": len(documents),
            "spins": documents  # Lista completa de documentos
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar histórico detalhado: {str(e)}"
        )


@router.get("/list/roulettes")
async def list_roulettes(request: Request) -> Dict:
    """
    Lista todas as roletas disponíveis no banco
    """
    try:
        db = request.app.state.db
        settings = request.app.state.settings
        
        collection = db[settings.MONGODB_COLLECTION]
        
        # Buscar roulette_ids distintos
        roulettes = await collection.distinct("roulette_id")
        
        # Contar documentos por roleta
        result = []
        for roulette_id in roulettes:
            count = await collection.count_documents({"roulette_id": roulette_id})
            
            # Buscar último documento
            last_doc = await collection.find_one(
                {"roulette_id": roulette_id},
                sort=[("timestamp", -1)]
            )
            
            result.append({
                "roulette_id": roulette_id,
                "roulette_name": last_doc.get("roulette_name", roulette_id) if last_doc else roulette_id,
                "total_spins": count,
                "last_update": last_doc["timestamp"].isoformat() if last_doc else None
            })
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_roulettes": len(result),
            "roulettes": result
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao listar roletas: {str(e)}"
        )

