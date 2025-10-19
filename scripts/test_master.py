# ========== scripts/test_master.py ==========
"""
Script de teste do padrão MASTER

Execute: python scripts/test_master.py
"""

import sys
sys.path.append('.')

from patterns.master import MasterPattern


def test_master_basico():
    """Teste básico do padrão MASTER"""
    print("=" * 60)
    print("TESTE BÁSICO - PADRÃO MASTER")
    print("=" * 60)
    
    # Histórico de exemplo (mais recente primeiro)
    history = [
        3, 3, 27, 13, 36, 14, 11, 31, 28, 33, 24, 0, 36, 3, 26, 32,
        1, 6, 22, 35, 17, 28, 8, 11, 1, 31, 9, 7, 11, 30, 1, 2, 27,
        27, 22, 4, 19, 8, 17, 16, 29, 23, 22, 35, 20, 4, 24, 29
    ]
    
    print(f"\n📊 Histórico: {len(history)} números")
    print(f"Últimos 10: {history[:10]}")
    
    # Criar instância do MASTER
    master = MasterPattern(config={
        'janela_min': 2,
        'janela_max': 4,
        'decay_factor': 0.95,
        'min_support': 2
    })
    
    # Analisar
    print("\n🔍 Analisando com MASTER...\n")
    resultado = master.analyze(history)
    
    # Mostrar resultados
    print("\n✅ RESULTADOS:")
    print(f"Total de candidatos: {len(resultado.candidatos)}")
    print(f"Padrões encontrados: {resultado.metadata['padroes_encontrados']}")
    print(f"Janelas analisadas: {resultado.metadata['janelas_analisadas']}")
    
    # Top 10
    print("\n🎯 TOP 10 CANDIDATOS:")
    top_10 = resultado.get_top_n(10)
    for i, (numero, score) in enumerate(top_10, 1):
        print(f"   {i:2d}. Número {numero:2d} - Score: {score:.4f}")
    
    # Relações detectadas
    print("\n🔗 RELAÇÕES DETECTADAS:")
    relacoes = resultado.metadata['relacoes_detectadas']
    for tipo, qtd in relacoes.items():
        print(f"   {tipo.capitalize()}: {qtd}")
    
    print("\n" + "=" * 60)


def test_master_detalhado():
    """Teste com análise detalhada"""
    print("\n" + "=" * 60)
    print("TESTE DETALHADO - PADRÃO MASTER")
    print("=" * 60)
    
    history = [
        21, 30, 10, 28, 6, 13, 19, 6, 4, 5, 3, 8, 25, 28, 25,
        3, 3, 27, 13, 36, 14, 11, 31, 28, 33, 24, 0, 36, 3, 26
    ]
    
    master = MasterPattern()
    
    # Análise detalhada
    analise = master.get_analise_detalhada(history)
    
    print(f"\n📊 Histórico: {analise['historico_size']} números")
    print(f"Últimos 10: {analise['ultimos_10']}")
    
    print(f"\n⚙️ CONFIGURAÇÃO:")
    for key, value in analise['config'].items():
        print(f"   {key}: {value}")
    
    print(f"\n🎯 TOP 6 SUGESTÕES:")
    for i, (numero, score) in enumerate(analise['top_candidatos'][:6], 1):
        print(f"   {i}. Número {numero:2d} - Score: {score:.4f}")
    
    print("\n" + "=" * 60)


def test_master_comparacao():
    """Teste comparando diferentes configurações"""
    print("\n" + "=" * 60)
    print("TESTE COMPARAÇÃO - DIFERENTES CONFIGS")
    print("=" * 60)
    
    history = [
        3, 3, 27, 13, 36, 14, 11, 31, 28, 33, 24, 0, 36, 3, 26, 32,
        1, 6, 22, 35, 17, 28, 8, 11, 1, 31, 9, 7, 11, 30
    ]
    
    configs = [
        {'janela_min': 2, 'janela_max': 3, 'min_support': 2},
        {'janela_min': 3, 'janela_max': 5, 'min_support': 2},
        {'janela_min': 2, 'janela_max': 4, 'min_support': 1},
    ]
    
    for i, config in enumerate(configs, 1):
        print(f"\n--- Configuração {i} ---")
        print(f"Config: {config}")
        
        master = MasterPattern(config=config)
        resultado = master.analyze(history)
        
        top_5 = resultado.get_top_n(5)
        print(f"Top 5: {[n for n, s in top_5]}")
        print(f"Padrões encontrados: {resultado.metadata['padroes_encontrados']}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_master_basico()
    test_master_detalhado()
    test_master_comparacao()
