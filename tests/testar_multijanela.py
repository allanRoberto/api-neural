"""
tests/testar_multi_janela.py

Testa MASTER com análise de múltiplas janelas recentes
"""

import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import Settings
from patterns.master_melhorado import MasterPatternMelhorado


async def testar():
    """Testa multi-janela"""
    
    print("\n" + "="*70)
    print("🔄 TESTE: Análise de Múltiplas Janelas")
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
    ).sort("timestamp", -1).limit(2000)
    
    documents = await cursor.to_list(length=2000)
    historico = [doc.get("value", 0) for doc in documents]
    
    print(f"✅ {len(historico)} números carregados")
    print(f"Últimos 20: {historico[:20]}\n")
    
    # TESTE 1: Janela única (comportamento antigo)
    print("="*70)
    print("🔷 TESTE 1: Janela Única (offset=0 apenas)")
    print("="*70)
    
    config_unica = {
        "janela_min": 2,
        "janela_max": 2,
        "decay_factor": 0.95,
        "min_support": 1,
        "janelas_recentes": 1,  # Só última janela
    }
    
    master_unica = MasterPatternMelhorado(config=config_unica)
    resultado_unica = master_unica.analyze(historico)
    
    print(f"\nConfig: {config_unica}")
    print(f"Padrões encontrados: {resultado_unica.metadata.get('padroes_encontrados', 0)}")
    print(f"Janelas analisadas: {resultado_unica.metadata.get('janelas_analisadas', 0)}")
    print(f"Modo: {resultado_unica.metadata.get('modo', 'normal')}")
    print(f"\nTop 10:")
    
    for i, (num, score) in enumerate(resultado_unica.get_top_n(10), 1):
        print(f"  {i:2d}. Número {num:2d}: {score:.6f}")
    
    # TESTE 2: Múltiplas janelas (comportamento novo)
    print("\n" + "="*70)
    print("🔶 TESTE 2: Múltiplas Janelas (offset=0-4)")
    print("="*70)
    
    config_multi = {
        "janela_min": 2,
        "janela_max": 2,
        "decay_factor": 0.95,
        "min_support": 1,
        "janelas_recentes": 5,  # Últimas 5 janelas
    }
    
    master_multi = MasterPatternMelhorado(config=config_multi)
    resultado_multi = master_multi.analyze(historico)
    
    print(f"\nConfig: {config_multi}")
    print(f"Padrões encontrados: {resultado_multi.metadata.get('padroes_encontrados', 0)}")
    print(f"Janelas analisadas: {resultado_multi.metadata.get('janelas_analisadas', 0)}")
    print(f"Modo: {resultado_multi.metadata.get('modo', 'normal')}")
    print(f"\nTop 10:")
    
    for i, (num, score) in enumerate(resultado_multi.get_top_n(10), 1):
        print(f"  {i:2d}. Número {num:2d}: {score:.6f}")
    
    # TESTE 3: Muitas janelas
    print("\n" + "="*70)
    print("🔶 TESTE 3: Muitas Janelas (offset=0-9)")
    print("="*70)
    
    config_muitas = {
        "janela_min": 2,
        "janela_max": 2,
        "decay_factor": 0.95,
        "min_support": 1,
        "janelas_recentes": 10,  # Últimas 10 janelas
    }
    
    master_muitas = MasterPatternMelhorado(config=config_muitas)
    resultado_muitas = master_muitas.analyze(historico)
    
    print(f"\nConfig: {config_muitas}")
    print(f"Padrões encontrados: {resultado_muitas.metadata.get('padroes_encontrados', 0)}")
    print(f"Janelas analisadas: {resultado_muitas.metadata.get('janelas_analisadas', 0)}")
    print(f"Modo: {resultado_muitas.metadata.get('modo', 'normal')}")
    print(f"\nTop 10:")
    
    for i, (num, score) in enumerate(resultado_muitas.get_top_n(10), 1):
        print(f"  {i:2d}. Número {num:2d}: {score:.6f}")
    
    # COMPARAÇÃO
    print("\n\n" + "="*70)
    print("📊 COMPARAÇÃO")
    print("="*70)
    
    padroes_unica = resultado_unica.metadata.get('padroes_encontrados', 0)
    padroes_multi = resultado_multi.metadata.get('padroes_encontrados', 0)
    padroes_muitas = resultado_muitas.metadata.get('padroes_encontrados', 0)
    
    print(f"\nPadrões encontrados:")
    print(f"  Janela única:      {padroes_unica:3d}")
    print(f"  5 janelas:         {padroes_multi:3d} ({padroes_multi/max(padroes_unica,1):.1f}x)")
    print(f"  10 janelas:        {padroes_muitas:3d} ({padroes_muitas/max(padroes_unica,1):.1f}x)")
    
    # Top 1 de cada
    top_unica = resultado_unica.get_top_n(1)[0] if resultado_unica.candidatos else (None, 0)
    top_multi = resultado_multi.get_top_n(1)[0] if resultado_multi.candidatos else (None, 0)
    top_muitas = resultado_muitas.get_top_n(1)[0] if resultado_muitas.candidatos else (None, 0)
    
    print(f"\nTop 1:")
    print(f"  Janela única:  Número {top_unica[0]:2d} (score {top_unica[1]:.6f})")
    print(f"  5 janelas:     Número {top_multi[0]:2d} (score {top_multi[1]:.6f})")
    print(f"  10 janelas:    Número {top_muitas[0]:2d} (score {top_muitas[1]:.6f})")
    
    if padroes_multi > padroes_unica:
        print("\n✅ SUCESSO! Múltiplas janelas encontram MAIS padrões!")
        print(f"   Melhoria: {padroes_multi - padroes_unica} padrões a mais")
    else:
        print("\n⚠️  Múltiplas janelas não melhoraram...")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(testar())