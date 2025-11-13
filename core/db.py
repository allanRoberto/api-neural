# core/db.py
import os
import certifi
import pytz
import redis
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient

# ─── Conexão MongoDB / Motor ───────────────────────────────────────────────────
MONGO_URL = "mongodb+srv://revesbot:DlBnGmlimRZpIblr@cluster0.c14fnit.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
mongo_client = AsyncIOMotorClient(
    MONGO_URL,
    tls=True,
    tlsCAFile=certifi.where()
)
mongo_db     = mongo_client["roleta_db"]
history_coll = mongo_db["history"]

# Função utilitária (mantida aqui se outros módulos precisarem)
def format_timestamp_br(timestamp: int) -> str:
    tz = pytz.timezone("America/Sao_Paulo")
    dt = datetime.fromtimestamp(timestamp, tz)
    return dt.strftime("%d/%m/%Y %H:%M:%S")

predictions_norm_coll = mongo_db["predictions_normalized"]
