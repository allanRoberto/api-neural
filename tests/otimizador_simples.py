"""
tests/otimizador_simples.py

Otimizador SIMPLIFICADO - testa apenas configs de multi-janelas
"""

import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_assertividade import TestadorAssertividade


async def main():
    """Testa 3 configs de multi-janelas"""
    
    print("\n" + "="*70)
    print("🚀 TESTE SIMPLES: Multi-Janelas")
    print("="*70)
    
    roulette = "pragmatic-brazilian-roulette"
    num_testes = 50
    
    configs = {
        "1_janela": {
            "nome": "1 Janela (baseline)",
            "config": {
                "janela_min": 2,
                "janela_max": 2,
                "min_support": 1,
                "janelas_recentes": 1,
            }
        },
        "5_janelas": {
            "nome": "5 Janelas",
            "config": {
                "janela_min": 2,
                "janela_max": 2,
                "min_support": 1,
                "janelas_recentes": 5,
            }
        },
        "10_janelas": {
            "nome": "10 Janelas",
            "config": {
                "janela_min": 2,
                "janela_max": 2,
                "min_support": 1,
                "janelas_recentes": 10,
            }
        },
    }
    
    resultados = {}
    
    for config_id, config_data in configs.items():
        print(f"\n{'='*70}")
        print(f"🧪 {config_data['nome']}")
        print(f"{'='*70}")
        print(f"Config: {config_data['config']}")
        
        # Criar testador
        test_config = {
            'quantidade_testes': num_testes,
            'tamanho_verificacao': 60,
            'master_config': config_data['config']
        }
        
        testador = TestadorAssertividade(config=test_config)
        
        try:
            await testador.conectar_mongodb()
            relatorio = await testador.executar_backtesting(roulette)
            
            # Extrair métricas
            metricas = {
                'taxa_1': relatorio.taxa_acerto_acumulada.get(1, 0),
                'taxa_3': relatorio.taxa_acerto_acumulada.get(3, 0),
                'taxa_5': relatorio.taxa_acerto_acumulada.get(5, 0),
                'taxa_10': relatorio.taxa_acerto_acumulada.get(10, 0),
                'tempo_medio': relatorio.tempo_medio_acerto or 999,
            }
            
            resultados[config_id] = {
                'nome': config_data['nome'],
                'metricas': metricas
            }
            
            print(f"\n📊 Resultados:")
            print(f"  Taxa 1 giro:  {metricas['taxa_1']:.1f}%")
            print(f"  Taxa 3 giros: {metricas['taxa_3']:.1f}%")
            print(f"  Taxa 5 giros: {metricas['taxa_5']:.1f}%")
            print(f"  Tempo médio:  {metricas['tempo_medio']:.1f} giros")
            
            await testador.desconectar_mongodb()
            
        except Exception as e:
            print(f"❌ Erro: {e}")
            continue
    
    # Comparação
    print("\n\n" + "="*70)
    print("📊 COMPARAÇÃO FINAL")
    print("="*70)
    
    print(f"\n{'Config':<20} {'1g':<8} {'3g':<8} {'5g':<8} {'T.Méd':<8}")
    print("-" * 60)
    
    for config_id in ["1_janela", "5_janelas", "10_janelas"]:
        if config_id in resultados:
            r = resultados[config_id]
            m = r['metricas']
            print(
                f"{r['nome']:<20} "
                f"{m['taxa_1']:>5.1f}%  "
                f"{m['taxa_3']:>5.1f}%  "
                f"{m['taxa_5']:>5.1f}%  "
                f"{m['tempo_medio']:>5.1f}"
            )
    
    # Análise
    if len(resultados) >= 2:
        m1 = resultados.get('1_janela', {}).get('metricas', {})
        m5 = resultados.get('5_janelas', {}).get('metricas', {})
        
        if m1 and m5:
            diff_taxa = m5.get('taxa_5', 0) - m1.get('taxa_5', 0)
            diff_tempo = m1.get('tempo_medio', 999) - m5.get('tempo_medio', 999)
            
            print("\n" + "="*70)
            print("📈 MELHORIA COM MULTI-JANELAS:")
            print("="*70)
            
            if diff_taxa > 0:
                print(f"✅ Taxa 5 giros: +{diff_taxa:.1f}% melhor")
            else:
                print(f"⚠️  Taxa 5 giros: {diff_taxa:.1f}% (pior)")
            
            if diff_tempo > 0:
                print(f"✅ Tempo médio: {diff_tempo:.1f} giros mais rápido")
            else:
                print(f"⚠️  Tempo médio: {abs(diff_tempo):.1f} giros mais lento")
            
            if diff_taxa > 5:
                print("\n🎉 SUCESSO! Multi-janelas melhorou significativamente!")
            elif diff_taxa > 0:
                print("\n✅ Multi-janelas melhorou ligeiramente")
            else:
                print("\n⚠️  Multi-janelas não melhorou...")
                print("   Possíveis causas:")
                print("   - MASTER melhorado não está ativo")
                print("   - Histórico muito pequeno")
                print("   - Config não está sendo aplicada")


if __name__ == "__main__":
    asyncio.run(main())