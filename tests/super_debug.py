"""
tests/super_debug.py

Debug profundo para descobrir por que 0 padrões são encontrados
"""

import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import Settings
from utils.helpers import encontrar_sequencia


async def super_debug():
    """Debug completo"""
    
    print("\n" + "="*70)
    print("🔬 SUPER DEBUG - encontrar_sequencia")
    print("="*70)
    
    # Conectar
    settings = Settings()
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.MONGODB_DATABASE]
    collection = db[settings.MONGODB_COLLECTION]
    
    # Buscar histórico GRANDE
    print("\n📊 Buscando histórico...")
    cursor = collection.find(
        {"roulette_id": "pragmatic-brazilian-roulette"}
    ).sort("timestamp", -1).limit(2000)
    
    documents = await cursor.to_list(length=2000)
    historico = [doc.get("value", 0) for doc in documents]
    
    print(f"✅ {len(historico)} números carregados")
    print(f"Últimos 20: {historico[:20]}\n")
    
    # Testar diferentes janelas
    print("="*70)
    print("🔍 TESTE 1: Janela de tamanho 2")
    print("="*70)
    
    janela_2 = historico[:2]
    print(f"Sequência buscada: {janela_2}")
    print(f"Buscando no histórico (posições 2-{len(historico)})...\n")
    
    ocorrencias_2 = encontrar_sequencia(historico[2:], janela_2)
    
    print(f"✅ Encontradas: {len(ocorrencias_2)} ocorrências")
    
    if len(ocorrencias_2) > 0:
        print(f"Primeiras 5 posições: {ocorrencias_2[:5]}")
        
        # Mostrar contexto das primeiras 3
        for i, pos in enumerate(ocorrencias_2[:3]):
            pos_real = pos + 2  # Compensar offset
            contexto = historico[pos_real:pos_real+5]
            print(f"  Ocorrência {i+1} na posição {pos_real}: {contexto}")
    else:
        print("❌ NENHUMA ocorrência encontrada!")
        print("\nVamos procurar manualmente...")
        
        # Busca manual
        count_manual = 0
        for i in range(2, len(historico) - 1):
            if historico[i] == janela_2[0] and historico[i+1] == janela_2[1]:
                count_manual += 1
                if count_manual <= 3:
                    print(f"  Encontrado manualmente na posição {i}: {historico[i:i+5]}")
        
        print(f"\n🔍 Busca manual encontrou: {count_manual} ocorrências")
        
        if count_manual > 0:
            print("\n🚨 PROBLEMA: A função encontrar_sequencia NÃO está funcionando!")
        else:
            print("\n⚠️  A sequência realmente não se repete")
    
    # Teste com janela 3
    print("\n" + "="*70)
    print("🔍 TESTE 2: Janela de tamanho 3")
    print("="*70)
    
    janela_3 = historico[:3]
    print(f"Sequência buscada: {janela_3}")
    
    ocorrencias_3 = encontrar_sequencia(historico[3:], janela_3)
    
    print(f"✅ Encontradas: {len(ocorrencias_3)} ocorrências")
    
    if len(ocorrencias_3) == 0:
        # Busca manual
        count_manual = 0
        for i in range(3, len(historico) - 2):
            if (historico[i] == janela_3[0] and 
                historico[i+1] == janela_3[1] and 
                historico[i+2] == janela_3[2]):
                count_manual += 1
                if count_manual <= 3:
                    print(f"  Encontrado manualmente na posição {i}: {historico[i:i+5]}")
        
        print(f"\n🔍 Busca manual encontrou: {count_manual} ocorrências")
    
    # Teste com sequências comuns
    print("\n" + "="*70)
    print("🔍 TESTE 3: Sequências mais frequentes")
    print("="*70)
    
    # Encontrar pares mais comuns
    from collections import Counter
    pares = []
    for i in range(len(historico) - 1):
        par = (historico[i], historico[i+1])
        pares.append(par)
    
    pares_comuns = Counter(pares).most_common(10)
    
    print("Top 10 pares mais comuns:")
    for i, (par, freq) in enumerate(pares_comuns, 1):
        print(f"  {i:2d}. {list(par)} aparece {freq} vezes")
    
    # Testar com o par mais comum
    par_mais_comum = list(pares_comuns[0][0])
    print(f"\nTestando com o par mais comum: {par_mais_comum}")
    
    ocorrencias_comum = encontrar_sequencia(historico, par_mais_comum)
    print(f"✅ Encontradas pela função: {len(ocorrencias_comum)} ocorrências")
    print(f"Esperado: {pares_comuns[0][1]} ocorrências")
    
    if len(ocorrencias_comum) != pares_comuns[0][1]:
        print("\n🚨 DISCREPÂNCIA! A função encontrar_sequencia tem BUG!")
    else:
        print("\n✅ Função encontrar_sequencia funciona CORRETAMENTE")
    
    # Teste final: ver a implementação
    print("\n" + "="*70)
    print("📝 IMPLEMENTAÇÃO DA FUNÇÃO")
    print("="*70)
    
    import inspect
    codigo = inspect.getsource(encontrar_sequencia)
    print(codigo)
    
    client.close()


if __name__ == "__main__":
    asyncio.run(super_debug())