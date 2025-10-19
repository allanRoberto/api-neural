"""
tests/otimizador_master.py

Sistema de Otimização A/B do Padrão MASTER

Testa diferentes configurações para encontrar a melhor performance
"""

import sys
import os
import asyncio
from typing import List, Dict, Tuple
from datetime import datetime
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_assertividade import TestadorAssertividade


# =============================================================================
# CONFIGURAÇÕES A TESTAR
# =============================================================================

CONFIGS_TESTE = {
    "baseline": {
        "nome": "Baseline (atual)",
        "master_config": {
            "janela_min": 2,
            "janela_max": 4,
            "decay_factor": 0.95,
            "min_support": 2,
            "peso_relacoes": 0.5,  # Novo: peso das relações
        }
    },
    
    "janela_curta": {
        "nome": "Janela Curta (2-3)",
        "master_config": {
            "janela_min": 2,
            "janela_max": 3,
            "decay_factor": 0.95,
            "min_support": 2,
        }
    },
    
    "decay_forte": {
        "nome": "Decay Forte (0.98)",
        "master_config": {
            "janela_min": 2,
            "janela_max": 4,
            "decay_factor": 0.98,
            "min_support": 2,
        }
    },
    
    "suporte_alto": {
        "nome": "Suporte Alto (3)",
        "master_config": {
            "janela_min": 2,
            "janela_max": 4,
            "decay_factor": 0.95,
            "min_support": 3,
        }
    },
    
    "combinado_1": {
        "nome": "Combinado: Janela 2-3 + Decay 0.98",
        "master_config": {
            "janela_min": 2,
            "janela_max": 3,
            "decay_factor": 0.98,
            "min_support": 2,
        }
    },
    
    "combinado_2": {
        "nome": "Combinado: Janela 2-3 + Suporte 3",
        "master_config": {
            "janela_min": 2,
            "janela_max": 3,
            "decay_factor": 0.95,
            "min_support": 3,
        }
    },
    
    "agressivo": {
        "nome": "Agressivo: Janela 2-3 + Decay 0.99 + Suporte 3",
        "master_config": {
            "janela_min": 2,
            "janela_max": 3,
            "decay_factor": 0.99,
            "min_support": 3,
        }
    },
    
    "ultra_recente": {
        "nome": "Ultra Recente: Decay 0.99 + Suporte 4",
        "master_config": {
            "janela_min": 2,
            "janela_max": 3,
            "decay_factor": 0.99,
            "min_support": 4,
        }
    },
}


# =============================================================================
# OTIMIZADOR
# =============================================================================

class OtimizadorMaster:
    """Otimizador que testa diferentes configurações do MASTER"""
    
    def __init__(self, roulette_id: str, num_testes: int = 50):
        self.roulette_id = roulette_id
        self.num_testes = num_testes
        self.resultados = {}
    
    async def executar_otimizacao(self):
        """Executa testes com todas as configurações"""
        print("\n" + "="*70)
        print("🚀 OTIMIZADOR MASTER - TESTE A/B")
        print("="*70)
        print(f"\nRoleta: {self.roulette_id}")
        print(f"Testes por config: {self.num_testes}")
        print(f"Total de configs: {len(CONFIGS_TESTE)}\n")
        
        for config_id, config_data in CONFIGS_TESTE.items():
            print(f"\n{'='*70}")
            print(f"🧪 Testando: {config_data['nome']}")
            print(f"{'='*70}")
            
            config_completa = {
                'quantidade_testes': self.num_testes,
                'tamanho_verificacao': 60,
                'master_config': config_data['master_config']
            }
            
            testador = TestadorAssertividade(config=config_completa)
            
            try:
                await testador.conectar_mongodb()
                relatorio = await testador.executar_backtesting(self.roulette_id)
                metricas = self._extrair_metricas(relatorio)
                
                self.resultados[config_id] = {
                    'nome': config_data['nome'],
                    'config': config_data['master_config'],
                    'metricas': metricas,
                    'relatorio': relatorio
                }
                
                self._mostrar_resumo(config_data['nome'], metricas)
                await testador.desconectar_mongodb()
                
            except Exception as e:
                print(f"❌ Erro: {e}")
                continue
        
        self._comparar_resultados()
        self._recomendar_melhor()
    
    def _extrair_metricas(self, relatorio) -> Dict:
        """Extrai métricas chave do relatório"""
        return {
            'taxa_1_giro': relatorio.taxa_acerto_acumulada.get(1, 0),
            'taxa_3_giros': relatorio.taxa_acerto_acumulada.get(3, 0),
            'taxa_5_giros': relatorio.taxa_acerto_acumulada.get(5, 0),
            'taxa_10_giros': relatorio.taxa_acerto_acumulada.get(10, 0),
            'tempo_medio': relatorio.tempo_medio_acerto or 999,
            'tempo_mediano': relatorio.tempo_mediano_acerto or 999,
            'tempo_moda': relatorio.tempo_moda_acerto or 999,
            'taxa_total': (relatorio.total_acertos / relatorio.total_testes * 100),
        }
    
    def _mostrar_resumo(self, nome: str, metricas: Dict):
        """Mostra resumo das métricas"""
        print(f"\n📊 Resumo - {nome}:")
        print(f"   1 giro:  {metricas['taxa_1_giro']:5.1f}%")
        print(f"   3 giros: {metricas['taxa_3_giros']:5.1f}%")
        print(f"   5 giros: {metricas['taxa_5_giros']:5.1f}%")
        print(f"   Tempo médio: {metricas['tempo_medio']:.1f} giros")
    
    def _comparar_resultados(self):
        """Compara todos os resultados lado a lado"""
        print("\n\n" + "="*70)
        print("📊 COMPARAÇÃO DE RESULTADOS")
        print("="*70)
        
        print(f"\n{'Config':<30} {'1g':<8} {'3g':<8} {'5g':<8} {'T.Méd':<8}")
        print("-" * 70)
        
        for config_id, resultado in self.resultados.items():
            m = resultado['metricas']
            print(
                f"{resultado['nome']:<30} "
                f"{m['taxa_1_giro']:>5.1f}%  "
                f"{m['taxa_3_giros']:>5.1f}%  "
                f"{m['taxa_5_giros']:>5.1f}%  "
                f"{m['tempo_medio']:>5.1f}"
            )
    
    def _recomendar_melhor(self):
        """Recomenda a melhor configuração"""
        print("\n\n" + "="*70)
        print("🏆 RECOMENDAÇÕES")
        print("="*70)
        
        # Score ponderado
        scores = {}
        for config_id, resultado in self.resultados.items():
            m = resultado['metricas']
            
            # Fórmula balanceada
            score = (
                m['taxa_5_giros'] * 0.4 +
                m['taxa_3_giros'] * 0.3 +
                (100 - min(m['tempo_medio'], 100)) * 0.3
            )
            
            scores[config_id] = score
        
        # Ranking
        ranking = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        print(f"\n{'Rank':<6} {'Config':<30} {'Score':<10}")
        print("-" * 50)
        
        for rank, (config_id, score) in enumerate(ranking, 1):
            nome = self.resultados[config_id]['nome']
            print(f"{rank:<6} {nome:<30} {score:>6.1f}")
        
        # Recomendação final
        melhor_config_id = ranking[0][0]
        melhor_config = self.resultados[melhor_config_id]
        
        print("\n\n" + "="*70)
        print("✨ CONFIGURAÇÃO RECOMENDADA")
        print("="*70)
        print(f"\n{melhor_config['nome']}")
        print(f"Score: {ranking[0][1]:.1f}\n")
        print("Parâmetros:")
        for k, v in melhor_config['config'].items():
            print(f"   {k}: {v}")
        
        print("\nMétricas:")
        m = melhor_config['metricas']
        print(f"   Taxa 1 giro:  {m['taxa_1_giro']:.1f}%")
        print(f"   Taxa 3 giros: {m['taxa_3_giros']:.1f}%")
        print(f"   Taxa 5 giros: {m['taxa_5_giros']:.1f}%")
        print(f"   Tempo médio:  {m['tempo_medio']:.1f} giros")
    
    def salvar_resultados(self, filename: str = None):
        """Salva resultados em JSON"""
        if filename is None:
            os.makedirs('tests/resultados', exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tests/resultados/otimizacao_{self.roulette_id}_{timestamp}.json"
        
        dados = {}
        for config_id, resultado in self.resultados.items():
            dados[config_id] = {
                'nome': resultado['nome'],
                'config': resultado['config'],
                'metricas': resultado['metricas']
            }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Resultados salvos: {filename}")


# =============================================================================
# MAIN
# =============================================================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Otimizar configurações do MASTER')
    parser.add_argument('--roulette', type=str, default='pragmatic-brazilian-roulette')
    parser.add_argument('--tests', type=int, default=50)
    parser.add_argument('--save-json', action='store_true')
    
    args = parser.parse_args()
    
    otimizador = OtimizadorMaster(
        roulette_id=args.roulette,
        num_testes=args.tests
    )
    
    await otimizador.executar_otimizacao()
    
    if args.save_json:
        otimizador.salvar_resultados()


if __name__ == "__main__":
    asyncio.run(main())