"""
tests/testar_tamanhos.py

Testa MASTER com diferentes tamanhos de histórico
"""

import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import Settings
from patterns.master_melhorado import MasterPatternMelhorado


async def testar():
    """Testa diferentes tamanhos"""
    
    print("\n" + "="*70)
    print("📏 TESTE: Tamanho de histórico vs Padrões encontrados")
    print("="*70)
    
    # Conectar
    settings = Settings()
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.MONGODB_DATABASE]
    collection = db[settings.MONGODB_COLLECTION]
    
    # Buscar histórico COMPLETO
    print("\n📊 Buscando histórico completo...")
    cursor = collection.find(
        {"roulette_id": "pragmatic-brazilian-roulette"}
    ).sort("timestamp", -1).limit(5000)
    
    documents = await cursor.to_list(length=5000)
    historico_completo = [doc.get("value", 0) for doc in documents]
    
    print(f"✅ {len(historico_completo)} números carregados\n")
    
    # Testar diferentes tamanhos
    tamanhos = [100, 250, 500, 750, 1000, 1500, 2000, 3000]
    
    config = {
        "janela_min": 2,
        "janela_max": 3,
        "decay_factor": 0.95,
        "min_support": 1,  # Sensível
    }
    
    print("Config:", config)
    print()
    
    resultados = []
    
    for tamanho in tamanhos:
        if tamanho > len(historico_completo):
            break
        
        # Pegar os N números mais recentes
        historico = historico_completo[:tamanho]
        
        # Analisar
        master = MasterPatternMelhorado(config=config)
        resultado = master.analyze(historico)
        
        padroes = resultado.metadata.get('padroes_encontrados', 0)
        modo = resultado.metadata.get('modo', 'normal')
        
        resultados.append({
            'tamanho': tamanho,
            'padroes': padroes,
            'modo': modo
        })
        
        simbolo = "✅" if padroes > 0 else "❌"
        print(f"{simbolo} {tamanho:4d} números → {padroes:3d} padrões (modo: {modo})")
    
    # Análise
    print("\n" + "="*70)
    print("📊 ANÁLISE")
    print("="*70)
    
    primeiro_com_padrao = next((r for r in resultados if r['padroes'] > 0), None)
    
    if primeiro_com_padrao:
        print(f"\n✅ Mínimo para encontrar padrões: ~{primeiro_com_padrao['tamanho']} números")
        print(f"   Padrões encontrados: {primeiro_com_padrao['padroes']}")
    else:
        print("\n❌ Nenhum tamanho testado encontrou padrões!")
        print("   Problema pode ser com o min_support ou janela")
    
    # Recomendação
    print("\n" + "="*70)
    print("💡 RECOMENDAÇÃO")
    print("="*70)
    
    if primeiro_com_padrao:
        tamanho_recomendado = primeiro_com_padrao['tamanho'] * 2
        print(f"\nPara backtesting confiável, use:")
        print(f"   total_numeros >= {tamanho_recomendado}")
        print(f"\nNo arquivo test_assertividade.py:")
        print(f"   self.total_numeros = {tamanho_recomendado}")
    else:
        print("\nTente:")
        print("   1. min_support = 1")
        print("   2. janela_max = 2")
        print("   3. total_numeros >= 2000")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(testar())