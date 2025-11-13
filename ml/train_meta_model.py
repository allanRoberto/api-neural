# train_meta_model.py
"""
Treino do meta-modelo de sugestão.

Fluxo:
  - Carrega o dataset gerado pelo dataset_builder (meta_dataset.parquet ou .csv)
  - Separa treino e validação por ordem temporal (round_index)
  - Treina um RandomForestClassifier para prever y (1 se o número é o próximo, 0 caso contrário)
  - Calcula métricas, incluindo top-K accuracy por rodada
  - Salva o modelo treinado em disco (meta_model.joblib)
"""

from __future__ import annotations

import os
import time
from typing import Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    roc_auc_score,
    classification_report,
)

from ml_config import FEATURE_NAMES, DEFAULT_TOP_K


def load_dataset(dataset_path: str) -> pd.DataFrame:
    """
    Carrega o dataset de treino (parquet ou csv).
    """
    if dataset_path.lower().endswith(".parquet"):
        df = pd.read_parquet(dataset_path)
    elif dataset_path.lower().endswith(".csv"):
        df = pd.read_csv(dataset_path)
    else:
        raise ValueError(
            f"Extensão não suportada para dataset_path={dataset_path!r}. "
            f"Use .parquet ou .csv."
        )

    # Garantir tipos básicos
    df["round_index"] = df["round_index"].astype(int)
    df["number"] = df["number"].astype(int)
    df["y"] = df["y"].astype(int)

    return df


def train_val_split_by_round(df: pd.DataFrame, train_ratio: float = 0.8) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Faz split de treino/validação com base nos round_index (ordem temporal).

    train_ratio:
        Fração das rodadas (em ordem) usada para treino.
        Ex.: 0.8 -> 80% primeiras rodadas treino, 20% últimas validação.
    """
    unique_rounds = np.sort(df["round_index"].unique())
    n_rounds = len(unique_rounds)
    split_idx = int(n_rounds * train_ratio)

    train_rounds = set(unique_rounds[:split_idx])
    val_rounds = set(unique_rounds[split_idx:])

    train_df = df[df["round_index"].isin(train_rounds)].copy()
    val_df = df[df["round_index"].isin(val_rounds)].copy()

    return train_df, val_df


def train_meta_model(
    df: pd.DataFrame,
    model_output_path: str = "meta_model.joblib",
    top_k: int = DEFAULT_TOP_K,
    n_estimators: int = 200,
    max_depth: int = 10,
    n_jobs: int = -1,
) -> RandomForestClassifier:
    """
    Treina o RandomForestClassifier como meta-modelo.

    Params:
        df: DataFrame com colunas [round_index, number, y, FEATURE_NAMES...]
        model_output_path: caminho para salvar o modelo (joblib)
        top_k: K usado na métrica de top-K accuracy por rodada
        n_estimators, max_depth, n_jobs: hiperparâmetros do RandomForest

    Retorna:
        modelo treinado (RandomForestClassifier)
    """
    # Split temporal
    print("🔀 Separando treino e validação por round_index (ordem temporal)...")
    train_df, val_df = train_val_split_by_round(df, train_ratio=0.8)

    print(f"📊 Linhas treino: {len(train_df)}")
    print(f"📊 Linhas validação: {len(val_df)}")

    # Define X e y
    X_train = train_df[FEATURE_NAMES].values
    y_train = train_df["y"].values

    X_val = val_df[FEATURE_NAMES].values
    y_val = val_df["y"].values

    print("🧠 Inicializando RandomForestClassifier...")
    model = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        n_jobs=n_jobs,
        random_state=42,
        class_weight="balanced",  # <- importante
    )

    print("🚀 Treinando modelo...")
    t0 = time.perf_counter()
    model.fit(X_train, y_train)
    train_time = time.perf_counter() - t0
    print(f"⏱️  Tempo de treino: {train_time:.2f} s")

    # Métricas simples por linha
    print("📏 Avaliando no conjunto de validação (por linha)...")
    val_probs = model.predict_proba(X_val)[:, 1]
    val_pred = (val_probs >= 0.5).astype(int)

    acc = accuracy_score(y_val, val_pred)
    try:
        auc = roc_auc_score(y_val, val_probs)
    except ValueError:
        auc = float("nan")

    print(f"🔹 Accuracy (linha a linha): {acc:.6f}")
    print(f"🔹 ROC AUC: {auc:.6f}")
    print("🔹 Distribuição classe validação:")
    print(val_df["y"].value_counts(normalize=True))

    print("\n📝 Classification report (linha a linha):")
    print(classification_report(y_val, val_pred, digits=4))

    # Métrica importante: Top-K accuracy por rodada
    print(f"\n🎯 Calculando Top-{top_k} accuracy por rodada...")

    topk_hits = 0
    total_rounds = 0

    # Vamos usar o próprio val_df agrupado por round_index
    for round_id, group in val_df.groupby("round_index"):
        X_round = group[FEATURE_NAMES].values
        y_round = group["y"].values
        numbers_round = group["number"].values

        # probabilidade de ser o número correto
        probs_round = model.predict_proba(X_round)[:, 1]

        # número "verdadeiro" dessa rodada (onde y=1)
        true_idx = np.where(y_round == 1)[0]
        if len(true_idx) != 1:
            # isso não deveria acontecer, mas se acontecer, pula rodada
            continue

        true_number = numbers_round[true_idx[0]]

        # pega top_k índices ordenados por probabilidade
        top_indices = np.argsort(probs_round)[::-1][:top_k]
        top_numbers = set(numbers_round[idx] for idx in top_indices)

        if true_number in top_numbers:
            topk_hits += 1

        total_rounds += 1

    topk_acc = topk_hits / total_rounds if total_rounds > 0 else 0.0
    print(f"🎯 Top-{top_k} accuracy por rodada: {topk_acc:.6f} ({topk_hits}/{total_rounds})")

    # Salvar modelo
    print(f"\n💾 Salvando modelo em: {model_output_path}")
    joblib.dump(model, model_output_path)
    print("✅ Modelo salvo com sucesso.")

    return model


if __name__ == "__main__":
    """
    Execução direta:

        python train_meta_model.py

    Ajuste as variáveis abaixo conforme necessário.
    """
    DATASET_PATH = os.getenv("DATASET_PATH", "meta_dataset.parquet")
    MODEL_OUTPUT_PATH = os.getenv("MODEL_OUTPUT_PATH", "meta_model.joblib")
    TOP_K = int(os.getenv("TOP_K", str(DEFAULT_TOP_K)))

    print(f"📂 Carregando dataset de: {DATASET_PATH}")
    df = load_dataset(DATASET_PATH)

    print("🔣 Colunas disponíveis no dataset:")
    print(df.columns.tolist())

    # Sanidade rápida: garantir que todas as FEATURE_NAMES existam no dataset
    missing = [c for c in FEATURE_NAMES if c not in df.columns]
    if missing:
        raise SystemExit(f"As seguintes features definidas em ml_config.FEATURE_NAMES não existem no dataset: {missing}")

    model = train_meta_model(
        df=df,
        model_output_path=MODEL_OUTPUT_PATH,
        top_k=TOP_K,
        n_estimators=200,
        max_depth=10,
        n_jobs=-1,
    )
