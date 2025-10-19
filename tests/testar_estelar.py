"""
tests/testar_estelar.py

Testa o padrão ESTELAR individualmente
"""

import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import Settings
from patterns.estelar import EstelarPattern


async def testar():
    """Testa o ESTELAR"""
    
    print("\n" + "="*70)
    print("🌟 TESTE DO PADRÃO ESTELAR")
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
    
    # Config padrão
    config_padrao = {
        "estrutura_min": 2,
        "estrutura_max": 4,
        "min_support": 2,
    }
    
    print("="*70)
    print("🔶 ESTELAR - Config Padrão")
    print("="*70)
    print(f"Config: {config_padrao}\n")
    
    estelar = EstelarPattern(config=config_padrao)
    resultado = estelar.analyze(historico)
    
    print(f"Padrões equivalentes encontrados: {resultado.metadata.get('padroes_equivalentes', 0)}")
    print(f"Estruturas analisadas: {resultado.metadata.get('estruturas_analisadas', 0)}")
    print(f"\nTipos de equivalência detectados:")
    
    tipos = resultado.metadata.get('tipos_equivalencia', {})
    for tipo, count in sorted(tipos.items(), key=lambda x: x[1], reverse=True):
        print(f"  {tipo:15s}: {count:3d}")
    
    print(f"\nTop 10 candidatos:")
    for i, (num, score) in enumerate(resultado.get_top_n(10), 1):
        print(f"  {i:2d}. Número {num:2d}: {score:.6f}")
    
    # Teste com min_support = 1 (mais sensível)
    print("\n" + "="*70)
    print("🔶 ESTELAR - Mais Sensível (min_support=1)")
    print("="*70)
    
    config_sensivel = {
        "estrutura_min": 2,
        "estrutura_max": 3,
        "min_support": 1,
    }
    
    print(f"Config: {config_sensivel}\n")
    
    estelar_sensivel = EstelarPattern(config=config_sensivel)
    resultado_sensivel = estelar_sensivel.analyze(historico)
    
    print(f"Padrões equivalentes encontrados: {resultado_sensivel.metadata.get('padroes_equivalentes', 0)}")
    print(f"Estruturas analisadas: {resultado_sensivel.metadata.get('estruturas_analisadas', 0)}")
    print(f"\nTipos de equivalência detectados:")
    
    tipos_sensivel = resultado_sensivel.metadata.get('tipos_equivalencia', {})
    for tipo, count in sorted(tipos_sensivel.items(), key=lambda x: x[1], reverse=True):
        print(f"  {tipo:15s}: {count:3d}")
    
    print(f"\nTop 10 candidatos:")
    for i, (num, score) in enumerate(resultado_sensivel.get_top_n(10), 1):
        print(f"  {i:2d}. Número {num:2d}: {score:.6f}")
    
    # Comparar Top 10
    print("\n" + "="*70)
    print("📊 COMPARAÇÃO")
    print("="*70)
    
    top_padrao = [num for num, _ in resultado.get_top_n(10)]
    top_sensivel = [num for num, _ in resultado_sensivel.get_top_n(10)]
    
    if top_padrao == top_sensivel:
        print("\n⚠️  Os Top 10 são IDÊNTICOS")
    else:
        print("\n✅ Os Top 10 são DIFERENTES")
        print(f"\nPadrão:    {top_padrao}")
        print(f"Sensível:  {top_sensivel}")
        
        diferentes = len(set(top_padrao) - set(top_sensivel))
        print(f"\nNúmeros diferentes: {diferentes}/10")
    
    # Verificar se encontrou padrões
    padroes_padrao = resultado.metadata.get('padroes_equivalentes', 0)
    padroes_sensivel = resultado_sensivel.metadata.get('padroes_equivalentes', 0)
    
    print(f"\n\nPadrões Encontrados:")
    print(f"  Config padrão:   {padroes_padrao}")
    print(f"  Config sensível: {padroes_sensivel} ({padroes_sensivel/max(padroes_padrao,1):.1f}x)")
    
    if padroes_sensivel > 0:
        print("\n✅ ESTELAR está funcionando!")
    else:
        print("\n⚠️  ESTELAR não encontrou padrões equivalentes")
        print("   Possíveis causas:")
        print("   - Histórico muito curto")
        print("   - Configuração muito restritiva")
        print("   - Bug na lógica de equivalência")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(testar())