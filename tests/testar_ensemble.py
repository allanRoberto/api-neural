"""
tests/testar_ensemble.py

Testa o Ensemble MASTER + ESTELAR + CHAIN combinados
"""

import sys
import os
import asyncio
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import Settings
from patterns.master import MasterPattern
from patterns.estelar import EstelarPattern
from patterns.chain import ChainAnalyzer


async def testar():
    """Testa MASTER + ESTELAR + CHAIN"""
    
    print("\n" + "="*70)
    print("⚡ TESTE DO ENSEMBLE: MASTER + ESTELAR + CHAIN")
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
    
    # Configs
    config_master = {
        "janela_min": 2,
        "janela_max": 2,
        "min_support": 1,
        "janelas_recentes": 10,
    }
    
    config_estelar = {
        "estrutura_min": 2,
        "estrutura_max": 3,
        "min_support": 1,
    }
    
    config_chain = {
        "min_chain_support": 2,
        "chain_decay": 0.95,
        "recent_window_miss": 30,
        "max_chain_length": 4
    }
    
    # ==================================================================
    # TESTE 1: MASTER isolado
    # ==================================================================
    print("="*70)
    print("🔷 MASTER (isolado)")
    print("="*70)
    print(f"Config: {config_master}\n")
    
    master = MasterPattern(config=config_master)
    resultado_master = master.analyze(historico)
    
    print(f"Padrões encontrados: {resultado_master.metadata.get('padroes_encontrados', 0)}")
    print(f"Modo: {resultado_master.metadata.get('modo', 'normal')}")
    print(f"\nTop 10:")
    
    for i, (num, score) in enumerate(resultado_master.get_top_n(10), 1):
        print(f"  {i:2d}. Número {num:2d}: {score:.6f}")
    
    # ==================================================================
    # TESTE 2: ESTELAR isolado
    # ==================================================================
    print("\n" + "="*70)
    print("🌟 ESTELAR (isolado)")
    print("="*70)
    print(f"Config: {config_estelar}\n")
    
    estelar = EstelarPattern(config=config_estelar)
    resultado_estelar = estelar.analyze(historico)
    
    print(f"Padrões equivalentes: {resultado_estelar.metadata.get('padroes_equivalentes', 0)}")
    print(f"\nTipos de equivalência:")
    
    tipos = resultado_estelar.metadata.get('tipos_equivalencia', {})
    for tipo, count in sorted(tipos.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {tipo:15s}: {count:3d}")
    
    print(f"\nTop 10:")
    for i, (num, score) in enumerate(resultado_estelar.get_top_n(10), 1):
        print(f"  {i:2d}. Número {num:2d}: {score:.6f}")
    
    # ==================================================================
    # TESTE 3: CHAIN isolado
    # ==================================================================
    print("\n" + "="*70)
    print("🔗 CHAIN (isolado)")
    print("="*70)
    print(f"Config: {config_chain}\n")
    
    chain = ChainAnalyzer(config=config_chain)
    resultado_chain = chain.analyze(historico)
    
    print(f"Cadeias aprendidas: {resultado_chain.metadata.get('total_cadeias_aprendidas', 0)}")
    print(f"Inversões detectadas: {resultado_chain.metadata.get('inversoes_detectadas', 0)}")
    print(f"Compensações: {resultado_chain.metadata.get('compensacoes_detectadas', 0)}")
    
    # Top pares
    top_pares = resultado_chain.metadata.get('top_pares', [])[:5]
    if top_pares:
        print(f"\nTop 5 pares aprendidos:")
        for par in top_pares:
            print(f"  {par['de']:2d} → {par['para']:2d} ({par['vezes']}x)")
    
    print(f"\nTop 10:")
    for i, (num, score) in enumerate(resultado_chain.get_top_n(10), 1):
        print(f"  {i:2d}. Número {num:2d}: {score:.6f}")
    
    # ==================================================================
    # TESTE 4: ENSEMBLE (combinado com pesos dinâmicos)
    # ==================================================================
    print("\n" + "="*70)
    print("⚡ ENSEMBLE: MASTER + ESTELAR + CHAIN")
    print("="*70)
    
    # Pesos base do ensemble
    W_MASTER_BASE = 0.35
    W_ESTELAR_BASE = 0.35
    W_CHAIN_BASE = 0.30
    
    # Ajuste dinâmico baseado na quantidade de padrões
    padroes_master = resultado_master.metadata.get('padroes_encontrados', 0)
    padroes_estelar = resultado_estelar.metadata.get('padroes_equivalentes', 0)
    padroes_chain = resultado_chain.metadata.get('total_cadeias_aprendidas', 0)
    
    # Se CHAIN encontrou muitos padrões, aumenta seu peso
    if padroes_chain > 1000:
        W_CHAIN_BASE = 0.40
        W_MASTER_BASE = 0.30
        W_ESTELAR_BASE = 0.30
        print("\n⚡ Ajuste dinâmico: CHAIN com muitos padrões, aumentando peso!")
    
    # Normaliza pesos
    total_peso = W_MASTER_BASE + W_ESTELAR_BASE + W_CHAIN_BASE
    W_MASTER = W_MASTER_BASE / total_peso
    W_ESTELAR = W_ESTELAR_BASE / total_peso
    W_CHAIN = W_CHAIN_BASE / total_peso
    
    print(f"\nPesos (ajustados):")
    print(f"  MASTER:  {W_MASTER:.2f}")
    print(f"  ESTELAR: {W_ESTELAR:.2f}")
    print(f"  CHAIN:   {W_CHAIN:.2f}")
    
    # Combinar scores
    scores_combinados = defaultdict(float)
    
    # Adicionar scores do MASTER
    for num, score in resultado_master.scores.items():
        scores_combinados[num] += W_MASTER * score
    
    # Adicionar scores do ESTELAR
    for num, score in resultado_estelar.scores.items():
        scores_combinados[num] += W_ESTELAR * score
    
    # Adicionar scores do CHAIN
    for num, score in resultado_chain.scores.items():
        scores_combinados[num] += W_CHAIN * score
    
    # Normalizar
    if scores_combinados:
        max_score = max(scores_combinados.values())
        if max_score > 0:
            scores_combinados = {
                num: score / max_score
                for num, score in scores_combinados.items()
            }
    
    # Ordenar
    candidatos_ensemble = sorted(
        scores_combinados.keys(),
        key=lambda n: scores_combinados[n],
        reverse=True
    )
    
    print(f"\nTotal de candidatos: {len(candidatos_ensemble)}")
    print(f"\nTop 10 (Ensemble):")
    
    for i, num in enumerate(candidatos_ensemble[:10], 1):
        score = scores_combinados[num]
        
        # Verificar de onde veio
        tem_master = num in resultado_master.scores
        tem_estelar = num in resultado_estelar.scores
        tem_chain = num in resultado_chain.scores
        
        origem = []
        if tem_master:
            origem.append("M")
        if tem_estelar:
            origem.append("E")
        if tem_chain:
            origem.append("C")
        
        origem_str = "+".join(origem) if origem else "?"
        
        print(f"  {i:2d}. Número {num:2d}: {score:.6f} [{origem_str}]")
    
    # ==================================================================
    # COMPARAÇÃO DOS TOP 10
    # ==================================================================
    print("\n\n" + "="*70)
    print("📊 COMPARAÇÃO DOS TOP 10")
    print("="*70)
    
    top_master = [num for num, _ in resultado_master.get_top_n(10)]
    top_estelar = [num for num, _ in resultado_estelar.get_top_n(10)]
    top_chain = [num for num, _ in resultado_chain.get_top_n(10)]
    top_ensemble = candidatos_ensemble[:10]
    
    print(f"\nMASTER:   {top_master}")
    print(f"ESTELAR:  {top_estelar}")
    print(f"CHAIN:    {top_chain}")
    print(f"ENSEMBLE: {top_ensemble}")
    
    # ==================================================================
    # ANÁLISE DE SOBREPOSIÇÃO
    # ==================================================================
    print(f"\n\n" + "="*70)
    print("🎯 ANÁLISE DE SOBREPOSIÇÃO")
    print("="*70)
    
    set_master = set(top_master)
    set_estelar = set(top_estelar)
    set_chain = set(top_chain)
    set_ensemble = set(top_ensemble)
    
    # Consenso total (4/4)
    consenso_total = set_master & set_estelar & set_chain & set_ensemble
    print(f"\n✅ Consenso TOTAL (4/4): {len(consenso_total)} números")
    if consenso_total:
        print(f"   {sorted(consenso_total)}")
    
    # Consenso triplo (3/4)
    print(f"\n📊 Consenso TRIPLO (3/4):")
    
    mec = set_master & set_estelar & set_chain - consenso_total
    if mec:
        print(f"   M+E+C: {sorted(mec)}")
    
    mee = set_master & set_estelar & set_ensemble - consenso_total
    if mee:
        print(f"   M+E+Ens: {sorted(mee)}")
    
    mce = set_master & set_chain & set_ensemble - consenso_total
    if mce:
        print(f"   M+C+Ens: {sorted(mce)}")
    
    ece = set_estelar & set_chain & set_ensemble - consenso_total
    if ece:
        print(f"   E+C+Ens: {sorted(ece)}")
    
    # Consenso duplo (2/4)
    print(f"\n📊 Consenso DUPLO (2/4):")
    
    me = set_master & set_estelar - set_chain - set_ensemble - consenso_total
    if me:
        print(f"   M+E: {sorted(me)}")
    
    mc = set_master & set_chain - set_estelar - set_ensemble - consenso_total
    if mc:
        print(f"   M+C: {sorted(mc)}")
    
    ec = set_estelar & set_chain - set_master - set_ensemble - consenso_total
    if ec:
        print(f"   E+C: {sorted(ec)}")
    
    # Únicos
    print(f"\n📊 Únicos (1/4):")
    
    so_master = set_master - set_estelar - set_chain - set_ensemble
    if so_master:
        print(f"   Só MASTER: {sorted(so_master)}")
    
    so_estelar = set_estelar - set_master - set_chain - set_ensemble
    if so_estelar:
        print(f"   Só ESTELAR: {sorted(so_estelar)}")
    
    so_chain = set_chain - set_master - set_estelar - set_ensemble
    if so_chain:
        print(f"   Só CHAIN: {sorted(so_chain)}")
    
    so_ensemble = set_ensemble - set_master - set_estelar - set_chain
    if so_ensemble:
        print(f"   Só ENSEMBLE: {sorted(so_ensemble)}")
    
    # ==================================================================
    # ESTATÍSTICAS
    # ==================================================================
    print("\n\n" + "="*70)
    print("📈 ESTATÍSTICAS")
    print("="*70)
    
    print(f"\nPadrões detectados:")
    print(f"  MASTER:  {resultado_master.metadata.get('padroes_encontrados', 0)}")
    print(f"  ESTELAR: {resultado_estelar.metadata.get('padroes_equivalentes', 0)}")
    print(f"  CHAIN:   {resultado_chain.metadata.get('total_cadeias_aprendidas', 0)}")
    
    print(f"\nDetalhes CHAIN:")
    print(f"  Inversões: {resultado_chain.metadata.get('inversoes_detectadas', 0)}")
    print(f"  Compensações: {resultado_chain.metadata.get('compensacoes_detectadas', 0)}")
    
    cadeias_por_tam = resultado_chain.metadata.get('cadeias_por_tamanho', {})
    if cadeias_por_tam:
        print(f"\n  Cadeias por tamanho:")
        for tamanho, qtd in sorted(cadeias_por_tam.items()):
            print(f"    Tamanho {tamanho}: {qtd}")
    
    # ==================================================================
    # AVALIAÇÃO FINAL
    # ==================================================================
    print("\n\n" + "="*70)
    print("💡 AVALIAÇÃO FINAL")
    print("="*70)
    
    padroes_master = resultado_master.metadata.get('padroes_encontrados', 0)
    padroes_estelar = resultado_estelar.metadata.get('padroes_equivalentes', 0)
    padroes_chain = resultado_chain.metadata.get('total_cadeias_aprendidas', 0)
    
    # Status de cada padrão
    status = []
    if padroes_master > 0:
        status.append("MASTER ✅")
    if padroes_estelar > 0:
        status.append("ESTELAR ✅")
    if padroes_chain > 0:
        status.append("CHAIN ✅")
    
    print(f"\nPadrões ativos: {', '.join(status)}")
    
    # Análise de consenso
    if len(consenso_total) >= 3:
        print(f"\n✅ EXCELENTE! Consenso total em {len(consenso_total)} números")
        print("   Os 3 padrões concordam fortemente → alta confiança")
        print(f"   Sugestão: apostar em {sorted(consenso_total)}")
    elif len(consenso_total) >= 1:
        print(f"\n✅ BOM! Consenso total em {len(consenso_total)} números")
        print("   Algum consenso entre os 3 padrões")
    else:
        print(f"\n⚠️  Sem consenso total")
        
        # Verifica consenso triplo
        consenso_3 = len(mec) + len(mee) + len(mce) + len(ece)
        if consenso_3 >= 3:
            print(f"   Mas há {consenso_3} números com consenso triplo (3/4)")
    
    # Diversidade vs Consenso
    total_unicos = len(set_master | set_estelar | set_chain)
    total_consenso = len(consenso_total)
    
    if total_unicos > 0:
        taxa_consenso = (total_consenso / total_unicos) * 100
        print(f"\nDiversidade vs Consenso:")
        print(f"  Números únicos (união): {total_unicos}")
        print(f"  Consenso total: {total_consenso} ({taxa_consenso:.1f}%)")
        
        if taxa_consenso >= 30:
            print("  ✅ Alto consenso → confiança alta")
        elif taxa_consenso >= 15:
            print("  ⚖️  Consenso moderado → diversidade balanceada")
        else:
            print("  ⚠️  Baixo consenso → padrões divergentes")
    
    # Recomendação final
    print("\n\n" + "="*70)
    print("🎯 RECOMENDAÇÃO FINAL")
    print("="*70)
    
    if len(consenso_total) >= 2:
        print(f"\n✅ Apostar prioritariamente no consenso total:")
        print(f"   {sorted(consenso_total)}")
        
        if len(top_ensemble) > len(consenso_total):
            outros = [n for n in top_ensemble[:6] if n not in consenso_total]
            if outros:
                print(f"\n   Complementar com top do ensemble:")
                print(f"   {outros}")
    else:
        print(f"\n✅ Usar Top 6 do Ensemble (combinação ponderada):")
        print(f"   {top_ensemble[:6]}")
    
    # Identificar faltantes
    recent_30 = set(historico[:30])
    faltantes = [n for n in top_ensemble[:10] if n not in recent_30]
    
    if faltantes:
        print(f"\n⭐ FALTANTES (não apareceram nos últimos 30):")
        print(f"   {faltantes}")
        print(f"   Priorizar esses números!")
    
    print("\n" + "="*70)
    print("✅ TESTE CONCLUÍDO")
    print("="*70)
    
    client.close()


if __name__ == "__main__":
    asyncio.run(testar())