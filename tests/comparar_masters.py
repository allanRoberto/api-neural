"""
tests/comparar_masters.py

Compara MASTER original vs MASTER melhorado
"""

import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import Settings
from patterns.master import MasterPattern
from patterns.master_melhorado import MasterPatternMelhorado


async def comparar():
    """Compara os dois MASTERS"""
    
    print("\n" + "="*70)
    print("⚔️  MASTER ORIGINAL vs MASTER MELHORADO")
    print("="*70)
    
    # Conectar
    settings = Settings()
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.MONGODB_DATABASE]
    collection = db[settings.MONGODB_COLLECTION]
    
    # Buscar histórico
    print("\n📊 Buscando histórico...")
    cursor = collection.find(
        {"roulette_id": "pragmatic-brazilian-roulette"}
    ).sort("timestamp", -1).limit(500)
    
    documents = await cursor.to_list(length=500)
    historico = [doc.get("value", 0) for doc in documents]
    
    print(f"✅ {len(historico)} números carregados")
    print(f"Últimos 10: {historico[:10]}\n")
    
    # Config padrão
    config = {
        "janela_min": 2,
        "janela_max": 3,
        "decay_factor": 0.95,
        "min_support": 2,
    }
    
    # MASTER ORIGINAL
    print("="*70)
    print("🔷 MASTER ORIGINAL")
    print("="*70)
    
    master_original = MasterPattern(config=config)
    resultado_original = master_original.analyze(historico)
    
    print(f"\nParâmetros: {config}")
    print(f"Padrões encontrados: {resultado_original.metadata.get('padroes_encontrados', 0)}")
    print(f"Janelas analisadas: {resultado_original.metadata.get('janelas_analisadas', 0)}")
    print(f"\nTop 10:")
    
    for i, (num, score) in enumerate(resultado_original.get_top_n(10), 1):
        print(f"  {i:2d}. Número {num:2d}: {score:.6f}")
    
    # MASTER MELHORADO
    print("\n" + "="*70)
    print("🔶 MASTER MELHORADO")
    print("="*70)
    
    master_melhorado = MasterPatternMelhorado(config=config)
    resultado_melhorado = master_melhorado.analyze(historico)
    
    print(f"\nParâmetros: {config}")
    print(f"Padrões encontrados: {resultado_melhorado.metadata.get('padroes_encontrados', 0)}")
    print(f"Janelas analisadas: {resultado_melhorado.metadata.get('janelas_analisadas', 0)}")
    print(f"Modo: {resultado_melhorado.metadata.get('modo', 'normal')}")
    print(f"\nTop 10:")
    
    for i, (num, score) in enumerate(resultado_melhorado.get_top_n(10), 1):
        print(f"  {i:2d}. Número {num:2d}: {score:.6f}")
    
    # COMPARAÇÃO
    print("\n" + "="*70)
    print("📊 COMPARAÇÃO")
    print("="*70)
    
    top_orig = [num for num, _ in resultado_original.get_top_n(10)]
    top_mel = [num for num, _ in resultado_melhorado.get_top_n(10)]
    
    if top_orig == top_mel:
        print("\n⚠️  Os Top 10 são IDÊNTICOS")
    else:
        print("\n✅ Os Top 10 são DIFERENTES")
        print(f"\nOriginal:  {top_orig}")
        print(f"Melhorado: {top_mel}")
        
        # Quantos são diferentes
        diferentes = len(set(top_orig) - set(top_mel))
        print(f"\nNúmeros diferentes: {diferentes}/10")
    
    # Teste com min_support=1
    print("\n\n" + "="*70)
    print("🔶 MASTER MELHORADO (min_support=1)")
    print("="*70)
    
    config_sensivel = config.copy()
    config_sensivel['min_support'] = 1
    
    master_sensivel = MasterPatternMelhorado(config=config_sensivel)
    resultado_sensivel = master_sensivel.analyze(historico)
    
    print(f"\nParâmetros: {config_sensivel}")
    print(f"Padrões encontrados: {resultado_sensivel.metadata.get('padroes_encontrados', 0)}")
    print(f"Janelas analisadas: {resultado_sensivel.metadata.get('janelas_analisadas', 0)}")
    print(f"Modo: {resultado_sensivel.metadata.get('modo', 'normal')}")
    print(f"\nTop 10:")
    
    for i, (num, score) in enumerate(resultado_sensivel.get_top_n(10), 1):
        print(f"  {i:2d}. Número {num:2d}: {score:.6f}")
    
    top_sens = [num for num, _ in resultado_sensivel.get_top_n(10)]
    
    if top_sens != top_mel:
        print(f"\n✅ DIFERENTE do melhorado padrão!")
        print(f"Números diferentes: {len(set(top_sens) - set(top_mel))}/10")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(comparar())