"""
Gerenciador de conexão com MongoDB
CORRIGIDO: Comparação com None ao invés de bool()
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Gerencia conexão e operações com MongoDB
    Database: roleta_db
    Collection: history
    """
    
    def __init__(self, settings):
        self.settings = settings
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
    
    async def connect(self):
        """Conectar ao MongoDB"""
        try:
            self.client = AsyncIOMotorClient(
                self.settings.mongodb_url,
                maxPoolSize=self.settings.MONGODB_MAX_POOL_SIZE,
                minPoolSize=self.settings.MONGODB_MIN_POOL_SIZE,
            )
            self.db = self.client[self.settings.MONGODB_DATABASE]
            logger.info(f"✅ Conectado ao MongoDB: {self.settings.MONGODB_DATABASE}")
        except Exception as e:
            logger.error(f"❌ Erro ao conectar MongoDB: {e}")
            raise
    
    async def disconnect(self):
        """Desconectar do MongoDB"""
        if self.client is not None:  # ← CORRIGIDO
            self.client.close()
            logger.info("MongoDB desconectado")
    
    async def ping(self) -> bool:
        """Verificar conexão"""
        try:
            if self.client is None:  # ← CORRIGIDO
                return False
            await self.client.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"Erro no ping MongoDB: {e}")
            return False
    
    def get_database(self) -> AsyncIOMotorDatabase:
        """Retorna instância do database"""
        if self.db is None:  # ← CORRIGIDO: use 'is None' ao invés de 'not'
            raise Exception("Database não está conectado")
        return self.db
    
    async def create_indexes(self):
        """
        Criar índices necessários
        ADAPTADO: Sem round_id, usando _id do MongoDB
        """
        try:
            if self.db is None:  # ← CORRIGIDO
                raise Exception("Database não está conectado")
            
            collection = self.db[self.settings.MONGODB_COLLECTION]
            
            # Índice composto para consultas temporais
            await collection.create_index([
                ("roulette_id", 1),
                ("timestamp", -1)
            ], name="idx_roulette_timestamp")
            
            # Índice para filtro por valor (número)
            await collection.create_index([
                ("roulette_id", 1),
                ("value", 1)
            ], name="idx_roulette_value")
            
            # Índice apenas por timestamp (para queries temporais)
            await collection.create_index([
                ("timestamp", -1)
            ], name="idx_timestamp")
            
            logger.info("✅ Índices MongoDB criados/verificados")
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar índices: {e}")
            raise