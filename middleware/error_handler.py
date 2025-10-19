"""
Middleware para tratamento de erros
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


async def error_handler_middleware(request: Request, call_next):
    """
    Middleware para capturar e tratar erros
    """
    try:
        response = await call_next(request)
        return response
    
    except ValueError as e:
        logger.error(f"ValueError: {e}")
        return JSONResponse(
            status_code=400,
            content={
                "error": "Bad Request",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            }
        )
    
    except Exception as e:
        logger.error(f"Erro não tratado: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "Erro interno do servidor",
                "timestamp": datetime.now().isoformat(),
            }
        )
