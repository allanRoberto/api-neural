"""
tests/test_chain.py

Testa o padrão CHAIN individualmente com dados REAIS do MongoDB
"""

import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import Settings
from patterns.chain import ChainAnalyzer


async def testar():
    """Testa o CHAIN com dados reais"""
    
    print("\n" + "="*70)
    print("🔗 TESTE DO PADRÃO CHAIN")
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
    ).sort("timestamp", -1).limit(200)
    
    documents = await cursor.to_list(length=200)
    historico = [doc.get("value", 0) for doc in documents]
    
    print(f"✅ {len(historico)} números carregados")
    print(f"Últimos 20: {historico[:20]}\n")
    
    if len(historico) < 10:
        print("❌ Histórico insuficiente!")
        client.close()
        return
    
    # ==================================================================
    # TESTE 1: CONFIG PADRÃO
    # ==================================================================
    print("="*70)
    print("🔗 CHAIN - Config Padrão")
    print("="*70)
    
    config_padrao = {
        "min_chain_support": 2,
        "chain_decay": 0.95,
        "recent_window_miss": 30,
        "max_chain_length": 4
    }
    
    print(f"Config: {config_padrao}\n")
    
    chain = ChainAnalyzer(config=config_padrao)
    resultado = chain.analyze(historico)
    
    print(f"📈 RESULTADOS:")
    print(f"   • Total de candidatos: {len(resultado.candidatos)}")
    print(f"   • Cadeias aprendidas: {resultado.metadata.get('total_cadeias_aprendidas', 0)}")
    print(f"   • Inversões detectadas: {resultado.metadata.get('inversoes_detectadas', 0)}")
    print(f"   • Compensações detectadas: {resultado.metadata.get('compensacoes_detectadas', 0)}")
    
    # Cadeias por tamanho
    cadeias_por_tam = resultado.metadata.get('cadeias_por_tamanho', {})
    if cadeias_por_tam:
        print(f"\n   📊 Cadeias por tamanho:")
        for tamanho, qtd in sorted(cadeias_por_tam.items()):
            print(f"      • Tamanho {tamanho}: {qtd} cadeias")
    
    print(f"\nTop 10 candidatos:")
    for i, (num, score) in enumerate(resultado.get_top_n(10), 1):
        print(f"  {i:2d}. Número {num:2d}: {score:.6f}")
    
    # Top pares
    top_pares = resultado.metadata.get('top_pares', [])
    if top_pares:
        print(f"\nTop 10 pares aprendidos (X→Y):")
        for i, par in enumerate(top_pares[:10], 1):
            print(f"  {i:2d}. {par['de']:2d} → {par['para']:2d} ({par['vezes']}x)")
    
    # Inversões
    inversoes = resultado.metadata.get('inversoes', [])
    if inversoes:
        print(f"\nInversões detectadas:")
        for inv in inversoes[:5]:
            print(f"  • {inv['par_original']} ↔ {inv['par_invertido']} (dist: {inv['distancia']})")
    
    # ==================================================================
    # TESTE 2: CONFIG MAIS SENSÍVEL (min_support=1)
    # ==================================================================
    print("\n" + "="*70)
    print("🔗 CHAIN - Mais Sensível (min_support=1)")
    print("="*70)
    
    config_sensivel = {
        "min_chain_support": 1,
        "chain_decay": 0.97,
        "recent_window_miss": 30,
        "max_chain_length": 3
    }
    
    print(f"Config: {config_sensivel}\n")
    
    chain_sensivel = ChainAnalyzer(config=config_sensivel)
    resultado_sensivel = chain_sensivel.analyze(historico)
    
    print(f"📈 RESULTADOS:")
    print(f"   • Total de candidatos: {len(resultado_sensivel.candidatos)}")
    print(f"   • Cadeias aprendidas: {resultado_sensivel.metadata.get('total_cadeias_aprendidas', 0)}")
    print(f"   • Inversões detectadas: {resultado_sensivel.metadata.get('inversoes_detectadas', 0)}")
    
    print(f"\nTop 10 candidatos:")
    for i, (num, score) in enumerate(resultado_sensivel.get_top_n(10), 1):
        print(f"  {i:2d}. Número {num:2d}: {score:.6f}")
    
    # ==================================================================
    # TESTE 3: CONFIG RIGOROSO (min_support=3, decay menor)
    # ==================================================================
    print("\n" + "="*70)
    print("🔗 CHAIN - Rigoroso (min_support=3)")
    print("="*70)
    
    config_rigoroso = {
        "min_chain_support": 3,
        "chain_decay": 0.90,
        "recent_window_miss": 50,
        "max_chain_length": 4
    }
    
    print(f"Config: {config_rigoroso}\n")
    
    chain_rigoroso = ChainAnalyzer(config=config_rigoroso)
    resultado_rigoroso = chain_rigoroso.analyze(historico)
    
    print(f"📈 RESULTADOS:")
    print(f"   • Total de candidatos: {len(resultado_rigoroso.candidatos)}")
    print(f"   • Cadeias aprendidas: {resultado_rigoroso.metadata.get('total_cadeias_aprendidas', 0)}")
    print(f"   • Inversões detectadas: {resultado_rigoroso.metadata.get('inversoes_detectadas', 0)}")
    
    print(f"\nTop 10 candidatos:")
    for i, (num, score) in enumerate(resultado_rigoroso.get_top_n(10), 1):
        print(f"  {i:2d}. Número {num:2d}: {score:.6f}")
    
    # ==================================================================
    # COMPARAÇÃO DOS 3 TESTES
    # ==================================================================
    print("\n" + "="*70)
    print("📊 COMPARAÇÃO")
    print("="*70)
    
    top_padrao = [num for num, _ in resultado.get_top_n(10)]
    top_sensivel = [num for num, _ in resultado_sensivel.get_top_n(10)]
    top_rigoroso = [num for num, _ in resultado_rigoroso.get_top_n(10)]
    
    print(f"\nTop 10 de cada config:")
    print(f"  Padrão:    {top_padrao}")
    print(f"  Sensível:  {top_sensivel}")
    print(f"  Rigoroso:  {top_rigoroso}")
    
    # Consenso (números que aparecem em todas)
    set_padrao = set(top_padrao)
    set_sensivel = set(top_sensivel)
    set_rigoroso = set(top_rigoroso)
    
    consenso_total = set_padrao & set_sensivel & set_rigoroso
    if consenso_total:
        print(f"\n✅ Consenso total (3/3): {sorted(consenso_total)}")
    
    # Consenso duplo
    consenso_ps = set_padrao & set_sensivel - consenso_total
    consenso_pr = set_padrao & set_rigoroso - consenso_total
    consenso_sr = set_sensivel & set_rigoroso - consenso_total
    
    if consenso_ps or consenso_pr or consenso_sr:
        print(f"\nConsenso duplo (2/3):")
        if consenso_ps:
            print(f"  Padrão ∩ Sensível: {sorted(consenso_ps)}")
        if consenso_pr:
            print(f"  Padrão ∩ Rigoroso: {sorted(consenso_pr)}")
        if consenso_sr:
            print(f"  Sensível ∩ Rigoroso: {sorted(consenso_sr)}")
    
    # Estatísticas
    print(f"\n\nCadeias Aprendidas:")
    print(f"  Config padrão:   {resultado.metadata.get('total_cadeias_aprendidas', 0)}")
    print(f"  Config sensível: {resultado_sensivel.metadata.get('total_cadeias_aprendidas', 0)}")
    print(f"  Config rigoroso: {resultado_rigoroso.metadata.get('total_cadeias_aprendidas', 0)}")
    
    # ==================================================================
    # ANÁLISE DE FALTANTES (últimos 30 números)
    # ==================================================================
    print("\n" + "="*70)
    print("🎯 ANÁLISE DE FALTANTES (últimos 30)")
    print("="*70)
    
    recent_30 = set(historico[:30])
    top_10_padrao = resultado.get_top_n(10)
    
    faltantes = [(num, score) for num, score in top_10_padrao if num not in recent_30]
    
    if faltantes:
        print(f"\nNúmeros com alto score que NÃO apareceram nos últimos 30:")
        for num, score in faltantes:
            print(f"  • {num:2d}: score {score:.3f} ⭐ FALTANTE")
    else:
        print("\nTodos os top candidatos já apareceram recentemente")
    
    # ==================================================================
    # VERIFICAÇÃO DE CONTEXTO ATUAL
    # ==================================================================
    print("\n" + "="*70)
    print("🔍 VERIFICAÇÃO DE CONTEXTO ATUAL")
    print("="*70)
    
    ultimo = historico[0]
    print(f"\nÚltimo número: {ultimo}")
    
    # Busca pares que começam com o último número
    pares_do_ultimo = [p for p in top_pares if p['de'] == ultimo]
    if pares_do_ultimo:
        print(f"Cadeias ativas a partir de {ultimo}:")
        for par in pares_do_ultimo[:5]:
            print(f"  {ultimo} → {par['para']} (confiança: {par['vezes']}x)")
    else:
        print(f"Nenhuma cadeia forte ativa para {ultimo}")
    
    # ==================================================================
    # VALIDAÇÃO FINAL
    # ==================================================================
    print("\n" + "="*70)
    print("✅ VALIDAÇÃO")
    print("="*70)
    
    cadeias_padrao = resultado.metadata.get('total_cadeias_aprendidas', 0)
    cadeias_sensivel = resultado_sensivel.metadata.get('total_cadeias_aprendidas', 0)
    cadeias_rigoroso = resultado_rigoroso.metadata.get('total_cadeias_aprendidas', 0)
    
    if cadeias_padrao > 0 and cadeias_sensivel > cadeias_padrao:
        print("\n✅ CHAIN está funcionando corretamente!")
        print(f"   • Config sensível aprendeu mais: {cadeias_sensivel} vs {cadeias_padrao}")
        print(f"   • Config rigoroso aprendeu menos: {cadeias_rigoroso} (esperado)")
        print(f"   • Inversões detectadas: {resultado.metadata.get('inversoes_detectadas', 0)}")
        print(f"   • Compensações detectadas: {resultado.metadata.get('compensacoes_detectadas', 0)}")
    else:
        print("\n⚠️  CHAIN não encontrou cadeias suficientes")
        print("   Possíveis causas:")
        print("   - Histórico muito curto")
        print("   - Configuração muito restritiva")
        print("   - Padrões muito variáveis")
    
    # Resumo final
    print("\n" + "="*70)
    print("📋 RESUMO FINAL")
    print("="*70)
    
    print(f"\n📊 Dados analisados: {len(historico)} números")
    print(f"🎯 Sugestão principal (padrão): {top_padrao[0]} (score: {resultado.scores[top_padrao[0]]:.3f})")
    
    if consenso_total:
        print(f"⭐ Consenso total (3 configs): {sorted(consenso_total)}")
    
    print("\n" + "="*70)
    print("✅ TESTE CONCLUÍDO")
    print("="*70)
    
    client.close()


if __name__ == "__main__":
    asyncio.run(testar())