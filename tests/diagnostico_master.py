"""
tests/diagnostico_master.py

Diagnóstico para entender por que todas as configs dão resultado idêntico
"""

import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import Settings
from patterns.master import MasterPattern


async def diagnosticar():
    """Diagnóstico completo"""
    
    print("\n" + "="*70)
    print("🔍 DIAGNÓSTICO DO MASTER")
    print("="*70)
    
    # Conectar ao MongoDB
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
    print(f"Últimos 10: {historico[:10]}")
    
    # Testar 3 configurações diferentes
    configs = {
        "Config 1 (janela 2-4, support 2)": {
            "janela_min": 2,
            "janela_max": 4,
            "decay_factor": 0.95,
            "min_support": 2,
        },
        "Config 2 (janela 2-3, support 3)": {
            "janela_min": 2,
            "janela_max": 3,
            "decay_factor": 0.95,
            "min_support": 3,
        },
        "Config 3 (janela 2-3, decay 0.99, support 4)": {
            "janela_min": 2,
            "janela_max": 3,
            "decay_factor": 0.99,
            "min_support": 4,
        },
    }
    
    resultados = {}
    
    for nome, config in configs.items():
        print(f"\n{'='*70}")
        print(f"🧪 {nome}")
        print(f"{'='*70}")
        print(f"Parâmetros: {config}")
        
        # Criar instância do MASTER
        master = MasterPattern(config=config)
        
        # Verificar se config foi aplicado
        print(f"\nConfig aplicado no objeto:")
        print(f"  janela_min: {master.janela_min}")
        print(f"  janela_max: {master.janela_max}")
        print(f"  decay_factor: {master.decay_factor}")
        print(f"  min_support: {master.min_support}")
        
        # Analisar
        resultado = master.analyze(historico)
        
        # Mostrar top 10 COM scores
        print(f"\nTop 10 candidatos:")
        top_10 = resultado.get_top_n(10)
        for i, (num, score) in enumerate(top_10, 1):
            print(f"  {i:2d}. Número {num:2d}: {score:.6f}")
        
        # Guardar para comparação
        resultados[nome] = {
            'top_10': top_10,
            'metadata': resultado.metadata,
            'total_candidatos': len(resultado.candidatos)
        }
    
    # COMPARAÇÃO
    print(f"\n\n{'='*70}")
    print("📊 COMPARAÇÃO DE RESULTADOS")
    print("="*70)
    
    # Verificar se os Top 10 são diferentes
    tops = [r['top_10'] for r in resultados.values()]
    
    if len(set(str(t) for t in tops)) == 1:
        print("\n❌ PROBLEMA: Todos os resultados são IDÊNTICOS!")
        print("Isso indica que as configurações NÃO estão afetando o resultado.")
    else:
        print("\n✅ Os resultados são DIFERENTES!")
        print("As configurações estão funcionando corretamente.")
    
    # Mostrar diferenças nos scores
    print(f"\n\nComparação de scores do TOP 1:")
    for nome, res in resultados.items():
        if res['top_10']:
            num, score = res['top_10'][0]
            print(f"{nome:50s} → Número {num:2d} com score {score:.6f}")
    
    # Mostrar metadados
    print(f"\n\nMetadados (padrões encontrados):")
    for nome, res in resultados.items():
        padroes = res['metadata'].get('padroes_encontrados', 0)
        janelas = res['metadata'].get('janelas_analisadas', 0)
        print(f"{nome:50s} → {padroes} padrões em {janelas} janelas")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(diagnosticar())