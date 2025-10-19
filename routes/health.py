# ========== routes/health.py ==========
"""
Rota de Health Check
"""

from fastapi import APIRouter, Request
from datetime import datetime

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    """
    Verifica status da aplicação e MongoDB
    """
    try:
        # Testar conexão MongoDB
        db = request.app.state.db
        await db.command('ping')
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "version": "1.0.0"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "database": "disconnected",
            "error": str(e)
        }


@router.get("/ping")
async def ping():
    """
    Ping simples
    """
    return {"message": "pong", "timestamp": datetime.now().isoformat()}