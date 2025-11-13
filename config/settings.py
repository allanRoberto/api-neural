# ========== config/settings.py ==========
"""
Configurações centralizadas da aplicação
ADAPTADO PARA A ESTRUTURA REAL DO MONGODB
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """
    Configurações da aplicação usando Pydantic Settings
    """
    
    # ===== APLICAÇÃO =====
    APP_NAME: str = "Analizer Master + Estelar"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development, staging, production
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # ===== MONGODB =====
    MONGODB_HOST: str = "localhost"
    MONGODB_PORT: int = 27017
    MONGODB_USER: str = ""
    MONGODB_PASSWORD: str = ""
    MONGODB_DATABASE: str = "roleta_db"  # ← SEU DATABASE
    MONGODB_COLLECTION: str = "history"  # ← SUA COLLECTION
    MONGODB_MAX_POOL_SIZE: int = 10
    MONGODB_MIN_POOL_SIZE: int = 1
    MONGO_URL : str = "mongodb+srv://revesbot:DlBnGmlimRZpIblr@cluster0.c14fnit.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    
    # ===== CORS =====
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "*"  # Permitir todos em desenvolvimento
    ]
    
    # ===== CACHE =====
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 300  # 5 minutos
    
    # ===== PADRÕES (MASTER, ESTELAR, CHAIN) =====
    MASTER_JANELA_SIZE: int = 3
    MASTER_MIN_SUPPORT: float = 0.5
    MASTER_DECAY_FACTOR: float = 0.95
    
    ESTELAR_JANELA_SIZE: int = 3
    ESTELAR_MIN_SIMILARITY: float = 0.6
    
    CHAIN_MAX_LENGTH: int = 4
    CHAIN_MIN_SUPPORT: int = 2
    CHAIN_RECENT_WINDOW: int = 30
    
    # ===== ENSEMBLE =====
    W_MASTER: float = 1.0
    W_ESTELAR: float = 1.0
    W_CHAIN: float = 0.8
    W_TEMPORAL: float = 0.8
    
    # ===== TEMPORAL =====
    TEMPORAL_DEFAULT_INTERVAL: int = 5  # minutos
    TEMPORAL_DEFAULT_DAYS_BACK: int = 30
    TEMPORAL_MAX_DAYS_BACK: int = 365
    
    # ===== LIMITES =====
    MAX_SUGGESTIONS: int = 18
    MIN_SUGGESTIONS: int = 3
    DEFAULT_SUGGESTIONS: int = 6
    MIN_HISTORY_SIZE: int = 10
    MAX_HISTORY_SIZE: int = 500
    
    # ===== LOGGING =====
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "api.log"
    
    @property
    def mongodb_url(self) -> str:
        """Gera URL de conexão MongoDB"""
        if self.MONGODB_USER and self.MONGODB_PASSWORD:
            return f"mongodb+srv://{self.MONGODB_USER}:{self.MONGODB_PASSWORD}@{self.MONGODB_HOST}/?retryWrites=true&w=majority&appName=Cluster0"
        return f"mongodb://{self.MONGODB_HOST}:{self.MONGODB_PORT}/{self.MONGODB_DATABASE}"
    
    class Config:
        env_file = ".env"
        case_sensitive = True