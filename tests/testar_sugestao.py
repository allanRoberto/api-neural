"""
tests/testar_sugestao.py

Testa a rota /sugestao com diferentes configurações
"""

import sys
import os
import asyncio
import httpx

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


BASE_URL = "http://localhost:8000"


async def test_sugestao_basica():
    """Teste básico com configuração padrão"""
    print("\n" + "="*70)
    print("🎯 TESTE 1: SUGESTÃO BÁSICA (padrão)")
    print("="*70)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/sugestao/pragmatic-brazilian-roulette",
            params={
                "quantidade": 6
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n✅ Status: {response.status_code}")
            print(f"\nRoulette: {data['roulette_id']}")
            print(f"Último número: {data['analise']['ultimo_numero']}")
            print(f"Últimos 10: {data['analise']['ultimos_10']}")
            
            print(f"\n--- SUGESTÕES PRINCIPAIS ({len(data['sugestoes']['principais'])}) ---")
            for sug in data['sugestoes']['principais']:
                faltante = "⭐ FALTANTE" if sug['faltante'] else ""
                print(f"  {sug['ranking']}. Número {sug['numero']:2d} | "
                      f"Score: {sug['score']:.4f} | "
                      f"Consenso: {sug['consenso']} {faltante}")
            
            if data['sugestoes']['protecoes']:
                print(f"\n--- PROTEÇÕES ({len(data['sugestoes']['protecoes'])}) ---")
                for prot in data['sugestoes']['protecoes']:
                    print(f"  • {prot['numero']:2d} - {prot['tipo']}")
            
            print(f"\n--- CONSENSO ---")
            consenso = data['analise']['consenso']
            if consenso['consenso_total']:
                print(f"  ✅ Total (3/3): {consenso['consenso_total']}")
            
            for tipo, nums in consenso['consenso_duplo'].items():
                if nums:
                    print(f"  📊 Duplo {tipo}: {nums}")
            
            print(f"\n--- PADRÕES DETECTADOS ---")
            print(f"  MASTER:  {data['padroes']['master']['padroes_encontrados']} padrões")
            print(f"  ESTELAR: {data['padroes']['estelar']['padroes_equivalentes']} padrões")
            print(f"  CHAIN:   {data['padroes']['chain']['cadeias_aprendidas']} cadeias")
            
            print(f"\n--- CONFIGURAÇÃO ---")
            config = data['configuracao']
            print(f"  Pesos: M={config['pesos']['master']:.2f} "
                  f"E={config['pesos']['estelar']:.2f} "
                  f"C={config['pesos']['chain']:.2f}")
            print(f"  Histórico: {config['historico_analisado']} números")
            print(f"  Total protegido: {data['sugestoes']['total_numeros']} números")
            
            return data
        else:
            print(f"❌ Erro: {response.status_code}")
            print(response.text)
            return None


async def test_sugestao_sem_protecoes():
    """Teste sem proteções"""
    print("\n" + "="*70)
    print("🎯 TESTE 2: SEM PROTEÇÕES")
    print("="*70)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/sugestao/pragmatic-brazilian-roulette",
            params={
                "quantidade": 8,
                "incluir_protecoes": False
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n✅ Status: {response.status_code}")
            print(f"\nSugestões: {len(data['sugestoes']['principais'])}")
            print(f"Proteções: {len(data['sugestoes']['protecoes'])}")
            print(f"\nNúmeros sugeridos: {[s['numero'] for s in data['sugestoes']['principais']]}")
            
            return data
        else:
            print(f"❌ Erro: {response.status_code}")
            return None


async def test_sugestao_pesos_customizados():
    """Teste com pesos customizados"""
    print("\n" + "="*70)
    print("🎯 TESTE 3: PESOS CUSTOMIZADOS (CHAIN 50%)")
    print("="*70)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/sugestao/pragmatic-brazilian-roulette",
            params={
                "quantidade": 6,
                "w_master": 0.25,
                "w_estelar": 0.25,
                "w_chain": 0.50,
                "incluir_protecoes": True,
                "max_protecoes": 4
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n✅ Status: {response.status_code}")
            
            config = data['configuracao']
            print(f"\nPesos aplicados:")
            print(f"  MASTER:  {config['pesos']['master']:.2f}")
            print(f"  ESTELAR: {config['pesos']['estelar']:.2f}")
            print(f"  CHAIN:   {config['pesos']['chain']:.2f}")
            
            print(f"\n--- TOP 6 ---")
            for sug in data['sugestoes']['principais']:
                print(f"  {sug['ranking']}. Número {sug['numero']:2d} | "
                      f"Score: {sug['score']:.4f}")
            
            # Verifica influência do CHAIN
            chain_top3 = data['padroes']['chain']['top_3']
            principais = [s['numero'] for s in data['sugestoes']['principais']]
            
            sobreposicao = len(set(chain_top3) & set(principais))
            print(f"\nInfluência CHAIN:")
            print(f"  Top 3 CHAIN: {chain_top3}")
            print(f"  Sobreposição com sugestões: {sobreposicao}/3")
            
            return data
        else:
            print(f"❌ Erro: {response.status_code}")
            return None


async def test_sugestao_muitos_numeros():
    """Teste com muitos números e proteções"""
    print("\n" + "="*70)
    print("🎯 TESTE 4: MUITOS NÚMEROS (10 + 8 proteções)")
    print("="*70)
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/sugestao/pragmatic-brazilian-roulette",
            params={
                "quantidade": 10,
                "incluir_protecoes": True,
                "max_protecoes": 8,
                "incluir_zero": True
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n✅ Status: {response.status_code}")
            print(f"\nTotal protegido: {data['sugestoes']['total_numeros']} números")
            print(f"  Principais: {len(data['sugestoes']['principais'])}")
            print(f"  Proteções: {len(data['sugestoes']['protecoes'])}")
            
            todos_numeros = ([s['numero'] for s in data['sugestoes']['principais']] +
                           [p['numero'] for p in data['sugestoes']['protecoes']])
            
            print(f"\nTodos os números: {sorted(todos_numeros)}")
            print(f"Zero incluído: {'Sim' if 0 in todos_numeros else 'Não'}")
            
            return data
        else:
            print(f"❌ Erro: {response.status_code}")
            return None


async def comparar_configs():
    """Compara diferentes configurações"""
    print("\n" + "="*70)
    print("📊 COMPARAÇÃO DE CONFIGURAÇÕES")
    print("="*70)
    
    configs = [
        {"nome": "Padrão", "params": {"quantidade": 6}},
        {"nome": "CHAIN 50%", "params": {"quantidade": 6, "w_chain": 0.50, "w_master": 0.25, "w_estelar": 0.25}},
        {"nome": "MASTER 50%", "params": {"quantidade": 6, "w_master": 0.50, "w_chain": 0.25, "w_estelar": 0.25}},
        {"nome": "Sem proteções", "params": {"quantidade": 6, "incluir_protecoes": False}},
    ]
    
    resultados = {}
    
    async with httpx.AsyncClient() as client:
        for config in configs:
            print(f"\n--- {config['nome']} ---")
            
            response = await client.get(
                f"{BASE_URL}/api/sugestao/pragmatic-brazilian-roulette",
                params=config['params'],
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                principais = [s['numero'] for s in data['sugestoes']['principais']]
                print(f"  Números: {principais}")
                
                faltantes = [s['numero'] for s in data['sugestoes']['principais'] if s['faltante']]
                if faltantes:
                    print(f"  Faltantes: {faltantes}")
                
                resultados[config['nome']] = principais
            else:
                print(f"  ❌ Erro: {response.status_code}")
    
    # Análise de sobreposição
    if len(resultados) > 1:
        print("\n\n--- ANÁLISE DE SOBREPOSIÇÃO ---")
        
        all_sets = {nome: set(nums) for nome, nums in resultados.items()}
        
        # Consenso total
        if all_sets:
            consenso = set.intersection(*all_sets.values())
            if consenso:
                print(f"\n✅ Consenso total (todas configs): {sorted(consenso)}")
            else:
                print("\n⚠️  Sem consenso total entre todas as configs")
        
        # Pares
        nomes = list(resultados.keys())
        for i in range(len(nomes)):
            for j in range(i+1, len(nomes)):
                comum = all_sets[nomes[i]] & all_sets[nomes[j]]
                if comum:
                    print(f"\n{nomes[i]} ∩ {nomes[j]}: {sorted(comum)}")


async def main():
    """Executa todos os testes"""
    print("\n" + "="*70)
    print("🧪 TESTES DA ROTA /sugestao")
    print("="*70)
    print("\n⚠️  Certifique-se de que a API está rodando:")
    print("   python main.py")
    print("\n")
    
    try:
        # Teste 1
        await test_sugestao_basica()
        input("\n[Pressione ENTER para continuar...]")
        
        # Teste 2
        await test_sugestao_sem_protecoes()
        input("\n[Pressione ENTER para continuar...]")
        
        # Teste 3
        await test_sugestao_pesos_customizados()
        input("\n[Pressione ENTER para continuar...]")
        
        # Teste 4
        await test_sugestao_muitos_numeros()
        input("\n[Pressione ENTER para continuar...]")
        
        # Comparação
        await comparar_configs()
        
        print("\n\n" + "="*70)
        print("✅ TODOS OS TESTES CONCLUÍDOS")
        print("="*70)
        
    except httpx.ConnectError:
        print("\n❌ ERRO: Não foi possível conectar à API")
        print("   Certifique-se de que a API está rodando em http://localhost:8000")
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())