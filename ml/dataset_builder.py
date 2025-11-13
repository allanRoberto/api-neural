# dataset_builder.py
"""
Construtor de dataset para o meta-modelo de sugestão.

Este módulo:
  - Lê o histórico da roleta a partir do MongoDB (roleta_db.history)
  - Constrói uma sequência de SpinEvent (numero + timestamp)
  - Usa o feature_extractor para gerar features por número
  - Gera um DataFrame com linhas (rodada, número)
  - Salva em CSV ou Parquet
  - Mostra progresso (%) e ETA durante a construção do dataset

Estrutura esperada no MongoDB (collection: history):

{
  "_id": ObjectId(...),
  "roulette_id": "evolution-xxxtreme-lightning-roulette",
  "roulette_name": "evolution-xxxtreme-lightning-roulette",
  "value": 26,
  "timestamp": ISODate("2025-08-19T18:37:28.872Z")
}
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Dict, Any, Optional
import time
import sys

import pandas as pd
from pymongo import MongoClient

from ml.ml_config import NUMBERS, FEATURE_NAMES, CONTEXT_WINDOW
from ml.feature_extractor import extract_features_for_state


# ==========================
# MODELO DE EVENTO
# ==========================

@dataclass
class SpinEvent:
    """
    Representa um giro da roleta.

    Attributes:
        number: número que saiu (0..36)
        timestamp: datetime do giro (timezone-aware ou naive, tanto faz,
                   desde que seja consistente)
    """
    number: int
    timestamp: datetime


# ==========================
# LEITURA DO MONGO
# ==========================

def load_events_from_mongo(
    mongo_uri: str,
    roulette_id: str,
    db_name: str = "roleta_db",
    collection_name: str = "history",
    days_back: Optional[int] = None,
    limit: Optional[int] = None,
) -> List[SpinEvent]:
    """
    Lê o histórico de uma roleta específica a partir do MongoDB.

    mongo_uri:
        URI de conexão do MongoDB (ex.: "mongodb+srv://user:pass@cluster/...")

    roulette_id:
        ID da roleta (ex.: "evolution-xxxtreme-lightning-roulette")

    db_name:
        Nome do banco. Default: "roleta_db"

    collection_name:
        Nome da collection. Default: "history"

    days_back:
        Se informado, filtra apenas os últimos X dias a partir de agora.
        Ex.: days_back=60 -> últimos 60 dias.

    limit:
        Se informado, limita o número máximo de documentos retornados
        (após o filtro e ordenação).

    Retorna:
        Lista de SpinEvent em ORDEM CRONOLÓGICA (mais antigo primeiro,
        mais recente por último).
    """
    client = MongoClient(mongo_uri)
    db = client[db_name]
    coll = db[collection_name]

    query: Dict[str, Any] = {
        "roulette_id": roulette_id,
    }

    if days_back is not None:
        now_utc = datetime.now(timezone.utc)
        start_dt = now_utc - timedelta(days=days_back)
        query["timestamp"] = {"$gte": start_dt}

    cursor = coll.find(query).sort("timestamp", 1)  # ascendente

    if limit is not None and limit > 0:
        cursor = cursor.limit(limit)

    events: List[SpinEvent] = []
    for doc in cursor:
        value = int(doc["value"])
        ts = doc["timestamp"]  # datetime (normalmente timezone-aware)
        events.append(SpinEvent(number=value, timestamp=ts))

    client.close()
    return events


# ==========================
# BUILD DO DATASET A PARTIR DE EVENTS (com progresso e ETA)
# ==========================

def _format_eta(seconds: float) -> str:
    if seconds == float("inf") or seconds != seconds:  # inf ou NaN
        return "--:--:--"
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def build_dataset_from_events(
    events: Iterable[SpinEvent],
    roulette_id: Optional[str] = None,
    show_progress: bool = True,
    use_tqdm: bool = True,
    plain_progress_step: int = 200,   # usado se tqdm não estiver disponível
) -> pd.DataFrame:
    """
    Constrói um DataFrame de treino a partir de uma sequência de SpinEvent.

    events:
        Iterable de SpinEvent, em ORDEM CRONOLÓGICA
        (mais antigo primeiro, mais recente por último).

    roulette_id:
        Opcional, se você quiser diferenciar padrões por mesa
        dentro do feature_extractor.

    show_progress:
        Se True, exibe progresso (%) e ETA durante a construção.

    use_tqdm:
        Se True, tenta usar tqdm se estiver instalado.

    plain_progress_step:
        Frequência (em número de rodadas) para atualizar o progresso
        no modo "plain" (sem tqdm). Ex.: a cada 200 rodadas imprime progresso.

    Retorna:
        DataFrame com colunas:
            - round_index
            - number
            - <FEATURE_NAMES...>
            - y
    """
    events_list: List[SpinEvent] = list(events)

    if len(events_list) <= CONTEXT_WINDOW:
        raise ValueError(
            f"Número de eventos insuficiente ({len(events_list)}) para CONTEXT_WINDOW={CONTEXT_WINDOW}"
        )

    rows: List[Dict[str, Any]] = []

    total_rounds = len(events_list) - CONTEXT_WINDOW
    start_time = time.perf_counter()
    use_progress_bar = False
    pbar = None

    if show_progress:
        if use_tqdm:
            try:
                from tqdm import tqdm  # type: ignore
                pbar = tqdm(total=total_rounds, desc="Construindo dataset", unit="rodadas")
                use_progress_bar = True
            except Exception:
                use_progress_bar = False

    # Loop das rodadas úteis
    for i in range(CONTEXT_WINDOW, len(events_list)):
        # Histórico: últimos CONTEXT_WINDOW giros
        window_events = events_list[i - CONTEXT_WINDOW : i]
        history = [ev.number for ev in reversed(window_events)]  # MAIS RECENTE no índice 0

        target_event = events_list[i]
        target_number = target_event.number
        now_dt = target_event.timestamp

        # Extrai features por número para esse estado
        features_by_number = extract_features_for_state(
            history=history,
            now_dt=now_dt,
            roulette_id=roulette_id,
        )

        # Uma linha por (rodada, número)
        for n in NUMBERS:
            feat_dict = features_by_number[n]

            row: Dict[str, Any] = {
                "round_index": i,
                "number": n,
                "y": 1 if n == target_number else 0,
            }

            for fname in FEATURE_NAMES:
                row[fname] = float(feat_dict.get(fname, 0.0))

            rows.append(row)

        # ======== Progresso / ETA ========
        if show_progress:
            done = (i - CONTEXT_WINDOW) + 1  # rodadas processadas
            if use_progress_bar and pbar is not None:
                pbar.update(1)
                # opcionalmente: pbar.set_postfix(...)
            else:
                # modo "plain" (sem tqdm): imprime a cada N passos
                if (done % plain_progress_step == 0) or (done == total_rounds):
                    elapsed = time.perf_counter() - start_time
                    rate = done / elapsed if elapsed > 0 else 0.0
                    remaining = total_rounds - done
                    eta = remaining / rate if rate > 0 else float("inf")
                    percent = (done / total_rounds) * 100.0
                    msg = (
                        f"\rProgresso: {percent:6.2f}%  "
                        f"({done}/{total_rounds})  "
                        f"ETA: {_format_eta(eta)}  "
                        f"Elapsed: {_format_eta(elapsed)}"
                    )
                    sys.stdout.write(msg)
                    sys.stdout.flush()

    if show_progress:
        if use_progress_bar and pbar is not None:
            pbar.close()
        else:
            sys.stdout.write("\n")
            sys.stdout.flush()

    df = pd.DataFrame(rows)
    total_elapsed = time.perf_counter() - start_time
    if show_progress:
        print(f"⏱️  Tempo total de construção: {_format_eta(total_elapsed)}")
    return df


# ==========================
# SALVAR DATASET
# ==========================

def save_dataset(
    df: pd.DataFrame,
    output_path: str,
) -> None:
    """
    Salva o DataFrame em CSV ou Parquet, dependendo da extensão.

    Ex:
        save_dataset(df, "meta_dataset.parquet")
        save_dataset(df, "meta_dataset.csv")
    """
    if output_path.lower().endswith(".parquet"):
        df.to_parquet(output_path, index=False)
    elif output_path.lower().endswith(".csv"):
        df.to_csv(output_path, index=False)
    else:
        raise ValueError(
            f"Extensão de arquivo não suportada para output_path={output_path!r}. "
            f"Use .parquet ou .csv."
        )


# ==========================
# EXEMPLO DE USO VIA __main__
# ==========================

if __name__ == "__main__":
    """
    Exemplo de uso direto deste módulo.

    Ajuste as variáveis abaixo e rode:

        python dataset_builder.py

    para gerar um arquivo de dataset local com barra de progresso/ETA.
    """
    import os

    # Ajuste aqui conforme seu ambiente
    MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://revesbot:DlBnGmlimRZpIblr@cluster0.c14fnit.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    ROULETTE_ID = os.getenv("ROULETTE_ID", "pragmatic-brazilian-roulette")
    DAYS_BACK = int(os.getenv("DAYS_BACK", "60"))   # ex.: últimos 60 dias
    LIMIT_ENV = os.getenv("LIMIT", "")
    LIMIT = int(LIMIT_ENV) if LIMIT_ENV.strip().isdigit() else None

    OUTPUT_PATH = os.getenv("OUTPUT_PATH", "meta_dataset.parquet")

    print(f"🔗 Conectando ao MongoDB: {MONGO_URI}")
    print(f"🎯 Lendo histórico da roleta: {ROULETTE_ID}")

    events = load_events_from_mongo(
        mongo_uri=MONGO_URI,
        roulette_id=ROULETTE_ID,
        db_name="roleta_db",
        collection_name="history",
        days_back=DAYS_BACK,
        limit=LIMIT,
    )

    print(f"📚 Eventos carregados: {len(events)}")

    if len(events) <= CONTEXT_WINDOW:
        raise SystemExit(
            f"Eventos insuficientes ({len(events)}) para CONTEXT_WINDOW={CONTEXT_WINDOW}"
        )

    print("⚙️  Construindo dataset a partir dos eventos (com progresso/ETA)...")
    df = build_dataset_from_events(
        events,
        roulette_id=ROULETTE_ID,
        show_progress=True,
        use_tqdm=True,           # se tiver tqdm instalado, usa barra; senão, cai no modo plain
        plain_progress_step=200, # se sem tqdm, atualiza a cada 200 rodadas
    )

    print(f"💾 Salvando dataset em: {OUTPUT_PATH}")
    save_dataset(df, OUTPUT_PATH)

    print("✅ Dataset gerado com sucesso!")
    print(df.head())
