"""
main.py - Aplicação Principal da API Analizer Master + Estelar

Arquitetura:
    - Separação de responsabilidades
    - Injeção de dependências
    - Padrões isolados (Master, Estelar, Chain)
    - Configurações centralizadas
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from motor.motor_asyncio import AsyncIOMotorClient
from typing import AsyncGenerator
import logging
import sys
from datetime import datetime

# Importar configurações
from config.settings import Settings
from config.database import DatabaseManager

# Importar rotas
from routes import sugestao, historico, analise, health

# Importar middleware customizado
from middleware.logging_middleware import LoggingMiddleware
from middleware.error_handler import error_handler_middleware

# ========== CONFIGURAÇÃO DE LOGGING ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('api.log')
    ]
)
logger = logging.getLogger(__name__)

# ========== CARREGAR CONFIGURAÇÕES ==========
settings = Settings()

# ========== GERENCIADOR DE BANCO DE DADOS ==========
db_manager = DatabaseManager(settings)

# ========== LIFESPAN (STARTUP/SHUTDOWN) ==========
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Gerencia o ciclo de vida da aplicação
    - Startup: Conecta ao MongoDB
    - Shutdown: Fecha conexões
    """
    # ===== STARTUP =====
    logger.info("🚀 Iniciando aplicação Analizer Master + Estelar...")
    
    try:
        # Conectar ao MongoDB
        await db_manager.connect()
        
        # Verificar conexão
        if await db_manager.ping():
            logger.info("✅ MongoDB conectado com sucesso")
        else:
            logger.error("❌ Falha na conexão com MongoDB")
            raise Exception("Não foi possível conectar ao MongoDB")
        
        # Criar índices necessários
        await db_manager.create_indexes()
        logger.info("✅ Índices MongoDB criados/verificados")
        
        # Injetar dependências na aplicação
        app.state.db = db_manager.get_database()
        app.state.settings = settings
        
        logger.info(f"✅ Aplicação iniciada na porta {settings.API_PORT}")
        logger.info(f"📊 Ambiente: {settings.ENVIRONMENT}")
        
    except Exception as e:
        logger.error(f"❌ Erro ao iniciar aplicação: {e}")
        raise
    
    yield
    
    # ===== SHUTDOWN =====
    logger.info("🔄 Encerrando aplicação...")
    
    try:
        await db_manager.disconnect()
        logger.info("✅ MongoDB desconectado com sucesso")
    except Exception as e:
        logger.error(f"❌ Erro ao desconectar MongoDB: {e}")
    
    logger.info("👋 Aplicação encerrada")

# ========== CRIAR APLICAÇÃO FASTAPI ==========
app = FastAPI(
    title="Analizer Master + Estelar API",
    description="""
    API para análise comportamental de roleta usando padrões Master, Estelar e Chain.
    
    ## Módulos:
    - **MASTER**: Análise de padrões exatos e recorrentes
    - **ESTELAR**: Análise de equivalências subjetivas
    - **CHAIN**: Análise contextual e dinâmica de fluxo
    - **TEMPORAL**: Filtro por horário em dados históricos
    
    ## Endpoints Principais:
    - `/api/sugestao/{roulette_id}` - Gerar sugestões
    - `/api/historico/{roulette_id}` - Buscar histórico
    - `/api/analise/{roulette_id}` - Análise detalhada
    - `/health` - Status da aplicação
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# ========== CONFIGURAR CORS ==========
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== MIDDLEWARE CUSTOMIZADO ==========
app.add_middleware(LoggingMiddleware)
app.middleware("http")(error_handler_middleware)

# ========== INCLUIR ROTAS ==========
app.include_router(
    sugestao.router,
    prefix="/api/sugestao",
    tags=["Sugestões"],
)

app.include_router(
    historico.router,
    prefix="/api/historico",
    tags=["Histórico"],
)

app.include_router(
    analise.router,
    prefix="/api/analise",
    tags=["Análise"],
)

app.include_router(
    health.router,
    prefix="",
    tags=["Health"],
)

# ========== ROTA RAIZ ==========
@app.get("/", tags=["Root"])
async def root():
    """
    Endpoint raiz - Informações da API
    """
    return {
        "app": "Analizer Master + Estelar",
        "version": "1.0.0",
        "status": "online",
        "timestamp": datetime.now().isoformat(),
        "environment": settings.ENVIRONMENT,
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
            "sugestao": "/api/sugestao/{roulette_id}",
            "historico": "/api/historico/{roulette_id}",
            "analise": "/api/analise/{roulette_id}",
        },
        "padroes_disponiveis": [
            "MASTER - Padrões exatos",
            "ESTELAR - Equivalências subjetivas",
            "CHAIN - Análise contextual",
            "TEMPORAL - Filtro por horário"
        ]
    }

# ========== TRATAMENTO DE EXCEÇÕES GLOBAIS ==========
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Tratador global de exceções
    """
    logger.error(f"❌ Erro não tratado: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc) if settings.ENVIRONMENT != "production" else "Erro interno do servidor",
            "timestamp": datetime.now().isoformat(),
        }
    )

# ========== EVENTOS CUSTOMIZADOS ==========
@app.on_event("startup")
async def log_startup():
    """
    Log adicional na inicialização
    """
    logger.info("=" * 60)
    logger.info("  ANALIZER MASTER + ESTELAR API")
    logger.info("=" * 60)
    logger.info(f"  Versão: 1.0.0")
    logger.info(f"  Ambiente: {settings.ENVIRONMENT}")
    logger.info(f"  MongoDB: {settings.MONGODB_HOST}:{settings.MONGODB_PORT}")
    logger.info(f"  Database: {settings.MONGODB_DATABASE}")
    logger.info("=" * 60)

# ========== MAIN (para execução direta) ==========
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.ENVIRONMENT == "development",
        log_level="info",
    )