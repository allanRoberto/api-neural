"""
analise_puxadas_completa.py

Análise completa de TODOS os números (0-36)
Descobre automaticamente os TOP números puxados por cada gatilho
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict, Counter
from typing import List, Dict, Tuple
import json
from datetime import datetime

# ==========================================
# CONFIGURAÇÕES - AJUSTE AQUI
# ==========================================

# Configurações
MONGODB_URL = "mongodb+srv://revesbot:DlBnGmlimRZpIblr@cluster0.c14fnit.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  # Ajuste conforme necessário
MONGODB_DATABASE = "roleta_db"
MONGODB_COLLECTION = "history"
ROULETTE_ID = "pragmatic-brazilian-roulette"

# Janelas de análise
JANELA_LOOKFORWARD = 2   # Jogadas À FRENTE
JANELA_LOOKBACK = 0      # Jogadas ANTES (já pago)

# Quantidade de histórico
LIMITE_HISTORICO = 70000

# Filtros de significância
MIN_OCORRENCIAS = 1      # Mínimo de aparições
MIN_LIFT = 0.2           # Lift mínimo para ser considerado relevante

# Quantos tops mostrar por número
TOP_N = 32

# ==========================================


class AnalisadorPuxadasCompleto:
    def __init__(self, db, collection_name: str):
        self.collection = db[collection_name]
        self.historico = []
        self.resultados_por_numero = {}  # {numero_gatilho: {analise completa}}
        self.resumo_geral = {
            'total_numeros_analisados': 0,
            'numeros_com_puxadas_fortes': [],
            'pares_mais_fortes': [],  # [(gatilho, puxado, lift)]
        }
    
    async def buscar_historico(self, roulette_id: str, limite: int) -> List[int]:
        """Busca histórico do MongoDB"""
        print(f"🔍 Buscando histórico de {roulette_id}...")
        
        cursor = self.collection.find(
            {"roulette_id": roulette_id}
        ).sort("timestamp", -1).limit(limite)
        
        documents = await cursor.to_list(length=limite)
        numeros = [doc.get("value", 0) for doc in documents]
        
        # Inverte para ordem cronológica (mais antigo primeiro)
        numeros = list(reversed(numeros))
        
        print(f"✅ Carregados {len(numeros)} números\n")
        return numeros
    
    def verificar_ja_pago(self, idx_ocorrencia: int, numero_candidato: int) -> bool:
        """Verifica se um número já foi pago antes do gatilho"""
        inicio = max(0, idx_ocorrencia - JANELA_LOOKBACK)
        fim = idx_ocorrencia
        janela_antes = self.historico[inicio:fim]
        return numero_candidato in janela_antes
    
    def analisar_numero_gatilho(self, numero_gatilho: int) -> Dict:
        """Analisa um número gatilho específico"""
        # Encontra todas as ocorrências
        ocorrencias = [i for i, num in enumerate(self.historico) if num == numero_gatilho]
        
        if len(ocorrencias) < 5:  # Mínimo de ocorrências
            return None
        
        # Contadores por número candidato
        contadores = {}
        for num in range(37):
            contadores[num] = {
                'aparicoes_geral': self.historico.count(num),
                'aparicoes_apos_gatilho': 0,
                'ocorrencias_validas': 0
            }
        
        # Analisa cada ocorrência
        for idx_ocorrencia in ocorrencias:
            inicio = idx_ocorrencia + 1
            fim = min(idx_ocorrencia + JANELA_LOOKFORWARD + 1, len(self.historico))
            janela_forward = self.historico[inicio:fim]
            
            # Conta aparições
            for num in janela_forward:
                ja_pago = self.verificar_ja_pago(idx_ocorrencia, num)
                if not ja_pago:
                    contadores[num]['aparicoes_apos_gatilho'] += 1
            
            # Conta ocorrências válidas
            for num in range(37):
                if not self.verificar_ja_pago(idx_ocorrencia, num):
                    contadores[num]['ocorrencias_validas'] += 1
        
        # Calcula estatísticas
        total_jogadas = len(self.historico)
        puxadas = {}
        
        for num, dados in contadores.items():
            if num == numero_gatilho:  # Pula o próprio número
                continue
            
            aparicoes_geral = dados['aparicoes_geral']
            aparicoes_apos = dados['aparicoes_apos_gatilho']
            ocorrencias_validas = dados['ocorrencias_validas']
            
            freq_geral = (aparicoes_geral / total_jogadas * 100) if total_jogadas > 0 else 0
            
            total_slots = ocorrencias_validas * JANELA_LOOKFORWARD
            freq_apos = (aparicoes_apos / total_slots * 100) if total_slots > 0 else 0
            
            lift = freq_apos / freq_geral if freq_geral > 0 else 0
            prob = (aparicoes_apos / ocorrencias_validas * 100) if ocorrencias_validas > 0 else 0
            
            if aparicoes_apos >= MIN_OCORRENCIAS and lift >= MIN_LIFT:
                puxadas[num] = {
                    'numero': num,
                    'vezes': aparicoes_apos,
                    'lift': round(lift, 2),
                    'prob': round(prob, 1),
                    'freq_geral': round(freq_geral, 2),
                    'freq_apos': round(freq_apos, 2)
                }
        
        # Ordena por lift
        top_puxados = sorted(puxadas.values(), key=lambda x: x['lift'], reverse=True)[:TOP_N]
        
        return {
            'numero_gatilho': numero_gatilho,
            'total_ocorrencias': len(ocorrencias),
            'top_puxados': top_puxados,
            'qtd_puxados_significativos': len(puxadas)
        }
    
    async def analisar_todos(self):
        """Analisa todos os números de 0 a 36"""
        print("="*90)
        print("🎯 ANÁLISE COMPLETA - TODOS OS NÚMEROS (0-36)")
        print("="*90)
        print(f"📏 Janela Forward: {JANELA_LOOKFORWARD} | Janela Lookback: {JANELA_LOOKBACK}")
        print(f"🎚️ Filtros: mín {MIN_OCORRENCIAS} vezes, lift ≥ {MIN_LIFT}x")
        print(f"📊 Histórico: {len(self.historico)} jogadas\n")
        
        numeros_analisados = 0
        
        for numero in range(37):
            print(f"🔄 Analisando número {numero}...", end=" ")
            
            resultado = self.analisar_numero_gatilho(numero)
            
            if resultado and len(resultado['top_puxados']) > 0:
                self.resultados_por_numero[numero] = resultado
                numeros_analisados += 1
                print(f"✅ {len(resultado['top_puxados'])} puxados encontrados")
            else:
                print("⚪ Sem puxadas significativas")
        
        print(f"\n✅ Análise concluída! {numeros_analisados}/37 números com puxadas significativas\n")
        
        # Gera resumo geral
        self.gerar_resumo_geral()
    
    def gerar_resumo_geral(self):
        """Gera estatísticas gerais da análise"""
        todos_pares = []
        
        for numero, dados in self.resultados_por_numero.items():
            for puxado in dados['top_puxados']:
                todos_pares.append({
                    'gatilho': numero,
                    'puxado': puxado['numero'],
                    'lift': puxado['lift'],
                    'vezes': puxado['vezes'],
                    'prob': puxado['prob']
                })
        
        # Top 20 pares mais fortes
        pares_ordenados = sorted(todos_pares, key=lambda x: x['lift'], reverse=True)
        self.resumo_geral['pares_mais_fortes'] = pares_ordenados[:20]
        
        # Números que têm puxadas fortes
        self.resumo_geral['numeros_com_puxadas_fortes'] = [
            {
                'numero': num,
                'qtd_puxados': len(dados['top_puxados']),
                'ocorrencias': dados['total_ocorrencias']
            }
            for num, dados in self.resultados_por_numero.items()
            if len(dados['top_puxados']) >= 3
        ]
        
        self.resumo_geral['total_numeros_analisados'] = len(self.resultados_por_numero)
    
    def exibir_relatorio_resumido(self):
        """Exibe relatório resumido"""
        print("="*90)
        print("📊 RELATÓRIO RESUMIDO")
        print("="*90)
        
        print(f"\n📈 Estatísticas Gerais:")
        print(f"   Total de números com puxadas: {self.resumo_geral['total_numeros_analisados']}/37")
        print(f"   Total de pares identificados: {len(self.resumo_geral['pares_mais_fortes'])}")
        
        print(f"\n🔥 TOP 20 PARES MAIS FORTES (GATILHO → PUXADO):")
        print(f"   {'Rank':<6} {'Gatilho→Puxado':<18} {'Lift':<10} {'Vezes':<10} {'Prob%'}")
        print(f"   {'-'*65}")
        
        for i, par in enumerate(self.resumo_geral['pares_mais_fortes'][:20], 1):
            gatilho = par['gatilho']
            puxado = par['puxado']
            lift = par['lift']
            vezes = par['vezes']
            prob = par['prob']
            
            status = "🔥🔥" if lift >= 2.0 else "🔥" if lift >= 1.5 else "✅"
            print(f"   {i:<6} {gatilho} → {puxado:<14} {lift:<10.2f}x {vezes:<10} {prob:.1f}%  {status}")
        
        print(f"\n🎯 Números com Mais Puxadas (≥3):")
        numeros_top = sorted(
            self.resumo_geral['numeros_com_puxadas_fortes'],
            key=lambda x: x['qtd_puxados'],
            reverse=True
        )[:15]
        
        for item in numeros_top:
            print(f"   Número {item['numero']}: {item['qtd_puxados']} puxados | {item['ocorrencias']} ocorrências")
        
        print("\n" + "="*90)
    
    def exibir_relatorio_detalhado(self, mostrar_top: int = 10):
        """Exibe relatório detalhado dos top N números"""
        print("\n" + "="*90)
        print(f"📋 RELATÓRIO DETALHADO - TOP {mostrar_top} NÚMEROS")
        print("="*90)
        
        # Ordena por quantidade de puxados
        numeros_ordenados = sorted(
            self.resultados_por_numero.items(),
            key=lambda x: len(x[1]['top_puxados']),
            reverse=True
        )[:mostrar_top]
        
        for numero, dados in numeros_ordenados:
            print(f"\n🎯 NÚMERO {numero} (apareceu {dados['total_ocorrencias']}x)")
            print(f"   Top {len(dados['top_puxados'])} puxados:")
            print(f"   {'#':<4} {'Nº':<6} {'Lift':<10} {'Vezes':<10} {'Prob%':<10} {'Status'}")
            print(f"   {'-'*55}")
            
            for i, puxado in enumerate(dados['top_puxados'][:32], 1):
                num = puxado['numero']
                lift = puxado['lift']
                vezes = puxado['vezes']
                prob = puxado['prob']
                
                if lift >= 2.0:
                    status = "🔥🔥 Muito Forte"
                elif lift >= 1.5:
                    status = "🔥 Forte"
                else:
                    status = "✅ Bom"
                
                print(f"   {i:<4} {num:<6} {lift:<10.2f}x {vezes:<10} {prob:<10.1f}% {status}")
    
    def salvar_json(self, filename: str = "analise_puxadas_completa.json"):
        """Salva todos os resultados em JSON"""
        resultado_final = {
            'parametros': {
                'janela_forward': JANELA_LOOKFORWARD,
                'janela_lookback': JANELA_LOOKBACK,
                'min_ocorrencias': MIN_OCORRENCIAS,
                'min_lift': MIN_LIFT,
                'top_n': TOP_N,
                'total_jogadas': len(self.historico)
            },
            'resumo_geral': self.resumo_geral,
            'analise_por_numero': self.resultados_por_numero,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(resultado_final, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Resultados completos salvos em: {filename}")


async def main():
    """Função principal"""
    print("\n🎯 ANÁLISE COMPLETA DE PUXADAS - TODOS OS NÚMEROS\n")
    
    # Conecta ao MongoDB
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[MONGODB_DATABASE]
    
    print(f"🔌 Conectado ao MongoDB: {MONGODB_DATABASE}")
    
    # Cria analisador
    analisador = AnalisadorPuxadasCompleto(db, MONGODB_COLLECTION)
    
    # Busca histórico
    analisador.historico = await analisador.buscar_historico(ROULETTE_ID, LIMITE_HISTORICO)
    
    if len(analisador.historico) < 100:
        print("❌ Histórico insuficiente para análise!")
        return
    
    # Analisa todos os números
    await analisador.analisar_todos()
    
    # Exibe relatórios
    analisador.exibir_relatorio_resumido()
    analisador.exibir_relatorio_detalhado(mostrar_top=37)
    
    # Salva JSON
    analisador.salvar_json()
    
    # Fecha conexão
    client.close()
    print("\n✅ Análise completa finalizada!\n")


if __name__ == "__main__":
    asyncio.run(main())