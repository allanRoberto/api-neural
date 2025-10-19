"""
tests/debug_profundo_offset.py

Debug INTERNO do _buscar_padroes_exatos_offset
"""

import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import Settings
from patterns.master import MasterPattern


async def debug():
    """Debug profundo"""
    
    print("\n" + "="*70)
    print("🔬 DEBUG PROFUNDO: _buscar_padroes_exatos_offset")
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
    print(f"Últimos 20: {historico[:20]}\n")
    
    # Config
    config = {
        "janela_min": 2,
        "janela_max": 2,
        "min_support": 1,
        "janelas_recentes": 5,
    }
    
    print(f"Config: {config}\n")
    
    # Criar master
    master = MasterPattern(config=config)
    
    # Simular o loop manualmente
    print("="*70)
    print("🔄 SIMULANDO LOOP DE BUSCA")
    print("="*70)
    
    janela_min = master.janela_min
    janela_max = master.janela_max
    janelas_recentes = master.janelas_recentes
    
    print(f"\nLimites do loop:")
    print(f"  janela_size: {janela_min} até {janela_max}")
    print(f"  offsets: 0 até {janelas_recentes-1}")
    print(f"  len(historico): {len(historico)}")
    
    total_chamadas = 0
    total_padroes = 0
    
    for janela_size in range(janela_min, janela_max + 1):
        print(f"\n{'─'*70}")
        print(f"Janela size = {janela_size}")
        print(f"{'─'*70}")
        
        for offset in range(janelas_recentes):
            # Replicar a lógica exata do código
            inicio = offset
            fim = offset + janela_size
            
            if fim > len(historico):
                print(f"  Offset {offset}: fim={fim} > len={len(historico)} → BREAK")
                break
            
            sequencia_atual = historico[inicio:fim]
            
            # Calcular busca_inicio
            busca_inicio = fim + janela_size
            
            if busca_inicio >= len(historico):
                print(f"  Offset {offset}: busca_inicio={busca_inicio} >= len={len(historico)} → BREAK")
                break
            
            print(f"\n  Offset {offset}:")
            print(f"    Sequência: {sequencia_atual} (posições {inicio}:{fim})")
            print(f"    Buscando de posição {busca_inicio} até {len(historico)}")
            
            # Buscar ocorrências
            from utils.helpers import encontrar_sequencia
            
            ocorrencias = encontrar_sequencia(
                historico[busca_inicio:],
                sequencia_atual
            )
            
            print(f"    Ocorrências encontradas: {len(ocorrencias)}")
            
            if len(ocorrencias) < master.min_support:
                print(f"    ❌ Menos que min_support ({master.min_support})")
                total_chamadas += 1
                continue
            
            # Contar padrões
            padroes_neste_offset = 0
            for idx_ocorrencia in ocorrencias:
                idx_real = idx_ocorrencia + busca_inicio
                
                if idx_real + 1 < len(historico):
                    numero_seguinte = historico[idx_real + 1]
                    padroes_neste_offset += 1
            
            print(f"    ✅ {padroes_neste_offset} padrões válidos")
            
            total_chamadas += 1
            total_padroes += padroes_neste_offset
    
    # Resumo
    print("\n\n" + "="*70)
    print("📊 RESUMO")
    print("="*70)
    
    print(f"\nTotal de chamadas realizadas: {total_chamadas}")
    print(f"Total de padrões encontrados: {total_padroes}")
    
    if total_padroes == 0:
        print("\n❌ PROBLEMA: 0 padrões encontrados!")
        print("\n🔍 Investigação:")
        
        # Teste manual simples
        print("\nTestando manualmente com a janela [0:2]:")
        seq_teste = historico[0:2]
        print(f"  Sequência: {seq_teste}")
        
        from utils.helpers import encontrar_sequencia
        
        ocorrencias_teste = encontrar_sequencia(historico[4:], seq_teste)
        print(f"  Ocorrências no resto: {len(ocorrencias_teste)}")
        
        if len(ocorrencias_teste) > 0:
            print(f"  Primeiras posições: {ocorrencias_teste[:5]}")
            print("\n✅ A função encontrar_sequencia FUNCIONA")
            print("❌ Mas a lógica do offset tem BUG!")
        else:
            print("\n⚠️  Essa sequência específica não se repete")
            print("   Tentando encontrar pares que se repetem...")
            
            from collections import Counter
            pares = []
            for i in range(len(historico) - 1):
                par = (historico[i], historico[i+1])
                pares.append(par)
            
            pares_comuns = Counter(pares).most_common(5)
            print(f"\n  Pares mais comuns:")
            for par, freq in pares_comuns:
                print(f"    {list(par)} aparece {freq} vezes")
            
            if pares_comuns[0][1] >= 2:
                print("\n✅ Existem pares que se repetem!")
                print("❌ O loop NÃO está encontrando eles!")
    else:
        print("\n✅ Padrões foram encontrados!")
        print(f"   Média: {total_padroes/total_chamadas:.1f} padrões por chamada")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(debug())