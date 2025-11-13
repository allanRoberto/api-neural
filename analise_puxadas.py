"""
analise_puxadas.py

Script para analisar padrão de "números que se puxam"
Valida se determinados números aparecem após um número gatilho
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict, Counter
from typing import List, Dict, Tuple
import json
from datetime import datetime

# Configurações
MONGODB_URL = "mongodb+srv://revesbot:DlBnGmlimRZpIblr@cluster0.c14fnit.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  # Ajuste conforme necessário
MONGODB_DATABASE = "roleta_db"
MONGODB_COLLECTION = "history"
ROULETTE_ID = "pragmatic-brazilian-roulette"

# Número que queremos analisar
NUMERO_GATILHO = 1

# Janelas de análise (CONFIGURE AQUI)
JANELA_LOOKFORWARD = 9   # Quantas jogadas À FRENTE analisar
JANELA_LOOKBACK = 0      # Quantas jogadas ANTES verificar (já pago)

# Quantidade de histórico
LIMITE_HISTORICO = 70000

# Filtros de significância
MIN_OCORRENCIAS = 3      # Mínimo de vezes que deve aparecer para ser considerado
MIN_LIFT = 1.0           # Lift mínimo para ser relevante (1.0 = mesma chance que baseline)

# ==========================================


class AnalisadorPuxadasAuto:
    def __init__(self, db, collection_name: str):
        self.collection = db[collection_name]
        self.resultados = {
            'numero_gatilho': NUMERO_GATILHO,
            'janela_forward': JANELA_LOOKFORWARD,
            'janela_lookback': JANELA_LOOKBACK,
            'total_ocorrencias_gatilho': 0,
            'ocorrencias_validas': 0,
            'total_jogadas_analisadas': 0,
            'puxadas_por_numero': {},  # {numero: {dados completos}}
            'top_10_puxados': [],
            'distribuicao_por_posicao': defaultdict(Counter)
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
        
        print(f"✅ Carregados {len(numeros)} números")
        return numeros
    
    def verificar_ja_pago(self, historico: List[int], idx_ocorrencia: int, numero_candidato: int) -> bool:
        """
        Verifica se um número específico já foi pago antes do gatilho
        
        Args:
            historico: Lista completa de números
            idx_ocorrencia: Índice da ocorrência do gatilho
            numero_candidato: Número que queremos verificar se já foi pago
        
        Returns:
            True se já foi pago, False caso contrário
        """
        # Pega a janela ANTES do gatilho
        inicio = max(0, idx_ocorrencia - JANELA_LOOKBACK)
        fim = idx_ocorrencia
        
        janela_antes = historico[inicio:fim]
        
        return numero_candidato in janela_antes
    
    def analisar_puxadas(self, historico: List[int]):
        """Analisa e descobre automaticamente os números mais puxados"""
        print(f"\n📊 Analisando puxadas do número {NUMERO_GATILHO}...")
        print(f"   📏 Janela forward: 1-{JANELA_LOOKFORWARD} jogadas à frente")
        print(f"   🔍 Janela lookback: {JANELA_LOOKBACK} jogadas antes (filtro 'já pago')")
        
        self.resultados['total_jogadas_analisadas'] = len(historico)
        
        # Encontra todas as ocorrências do número gatilho
        todas_ocorrencias = []
        for i, num in enumerate(historico):
            if num == NUMERO_GATILHO:
                todas_ocorrencias.append(i)
        
        self.resultados['total_ocorrencias_gatilho'] = len(todas_ocorrencias)
        print(f"   Número {NUMERO_GATILHO} apareceu {len(todas_ocorrencias)} vezes")
        
        if len(todas_ocorrencias) == 0:
            print("❌ Nenhuma ocorrência encontrada!")
            return
        
        # Para cada número possível (0-36), vamos contar:
        # 1. Quantas vezes aparece no geral
        # 2. Quantas vezes aparece após o gatilho (sem já pago)
        
        contadores_por_numero = {}
        
        for num_candidato in range(37):
            contadores_por_numero[num_candidato] = {
                'aparicoes_geral': historico.count(num_candidato),
                'aparicoes_apos_gatilho': 0,
                'ocorrencias_validas': 0,  # Para este número específico
                'aparicoes_por_posicao': defaultdict(int)
            }
        
        # Analisa cada ocorrência do gatilho
        for idx_ocorrencia in todas_ocorrencias:
            # Pega os próximos JANELA_LOOKFORWARD números
            inicio = idx_ocorrencia + 1
            fim = min(idx_ocorrencia + JANELA_LOOKFORWARD + 1, len(historico))
            
            janela_forward = historico[inicio:fim]
            
            # Para cada número na janela forward
            for pos_relativa, num in enumerate(janela_forward, start=1):
                # Verifica se este número já foi pago antes do gatilho
                ja_pago = self.verificar_ja_pago(historico, idx_ocorrencia, num)
                
                # Conta na distribuição geral por posição
                self.resultados['distribuicao_por_posicao'][pos_relativa][num] += 1
                
                if not ja_pago:
                    # Conta para este número
                    contadores_por_numero[num]['aparicoes_apos_gatilho'] += 1
                    contadores_por_numero[num]['aparicoes_por_posicao'][pos_relativa] += 1
        
        # Calcula ocorrências válidas (total de vezes que analisamos aquele número)
        for idx_ocorrencia in todas_ocorrencias:
            for num_candidato in range(37):
                ja_pago = self.verificar_ja_pago(historico, idx_ocorrencia, num_candidato)
                if not ja_pago:
                    contadores_por_numero[num_candidato]['ocorrencias_validas'] += 1
        
        # Calcula estatísticas para cada número
        total_jogadas = len(historico)
        
        for num, dados in contadores_por_numero.items():
            aparicoes_geral = dados['aparicoes_geral']
            aparicoes_apos = dados['aparicoes_apos_gatilho']
            ocorrencias_validas = dados['ocorrencias_validas']
            
            # Frequência geral
            freq_geral = (aparicoes_geral / total_jogadas * 100) if total_jogadas > 0 else 0
            
            # Frequência após gatilho (apenas ocorrências válidas)
            total_slots_validos = ocorrencias_validas * JANELA_LOOKFORWARD
            freq_apos_gatilho = (
                aparicoes_apos / total_slots_validos * 100 
                if total_slots_validos > 0 else 0
            )
            
            # Lift (correlação)
            lift = freq_apos_gatilho / freq_geral if freq_geral > 0 else 0
            
            # Probabilidade de aparecer pelo menos 1 vez na janela
            prob_aparecer = (aparicoes_apos / ocorrencias_validas * 100) if ocorrencias_validas > 0 else 0
            
            self.resultados['puxadas_por_numero'][num] = {
                'numero': num,
                'aparicoes_geral': aparicoes_geral,
                'aparicoes_apos_gatilho': aparicoes_apos,
                'ocorrencias_validas': ocorrencias_validas,
                'freq_geral': round(freq_geral, 2),
                'freq_apos_gatilho': round(freq_apos_gatilho, 2),
                'lift': round(lift, 2),
                'prob_aparecer': round(prob_aparecer, 2),
                'aparicoes_por_posicao': dict(dados['aparicoes_por_posicao'])
            }
        
        # Filtra e ordena para pegar TOP 10
        numeros_filtrados = [
            dados for num, dados in self.resultados['puxadas_por_numero'].items()
            if dados['aparicoes_apos_gatilho'] >= MIN_OCORRENCIAS
            and dados['lift'] >= MIN_LIFT
            and num != NUMERO_GATILHO  # Exclui o próprio gatilho
        ]
        
        # Ordena por lift (correlação)
        numeros_ordenados = sorted(numeros_filtrados, key=lambda x: x['lift'], reverse=True)
        
        self.resultados['top_10_puxados'] = numeros_ordenados[:10]
        self.resultados['ocorrencias_validas'] = todas_ocorrencias[0] if todas_ocorrencias else 0
        
        print(f"   ✅ Análise concluída!")
        print(f"   🔝 Identificados {len(numeros_ordenados)} números com correlação significativa")
    
    def exibir_relatorio(self):
        """Exibe relatório formatado"""
        print("\n" + "="*90)
        print(f"📊 RELATÓRIO - NÚMEROS PUXADOS PELO {NUMERO_GATILHO}")
        print("="*90)
        
        print(f"\n📋 Parâmetros:")
        print(f"   Número Gatilho: {NUMERO_GATILHO}")
        print(f"   Janela Forward: 1-{JANELA_LOOKFORWARD} jogadas à frente")
        print(f"   Janela Lookback: {JANELA_LOOKBACK} jogadas antes (filtro 'já pago')")
        print(f"   Total de jogadas analisadas: {self.resultados['total_jogadas_analisadas']}")
        print(f"   Ocorrências do gatilho: {self.resultados['total_ocorrencias_gatilho']}")
        print(f"   Filtros: mín {MIN_OCORRENCIAS} aparições, lift ≥ {MIN_LIFT}x")
        
        if not self.resultados['top_10_puxados']:
            print("\n⚠️ Nenhum número com correlação significativa encontrado!")
            return
        
        print(f"\n🏆 TOP 10 NÚMEROS MAIS PUXADOS:")
        print(f"   {'Rank':<6} {'Nº':<5} {'Vezes':<8} {'Lift':<8} {'Prob%':<8} {'Freq Geral':<12} {'Freq Pós':<12} {'Status'}")
        print(f"   {'-'*85}")
        
        for i, dados in enumerate(self.resultados['top_10_puxados'], 1):
            num = dados['numero']
            vezes = dados['aparicoes_apos_gatilho']
            lift = dados['lift']
            prob = dados['prob_aparecer']
            freq_geral = dados['freq_geral']
            freq_pos = dados['freq_apos_gatilho']
            
            # Status visual
            if lift >= 2.0:
                status = "🔥🔥 MUITO FORTE"
            elif lift >= 1.5:
                status = "🔥 FORTE"
            elif lift >= 1.2:
                status = "✅ BOM"
            else:
                status = "⚪ OK"
            
            print(f"   {i:<6} {num:<5} {vezes:<8} {lift:<8.2f}x {prob:<8.1f}% {freq_geral:<12.2f}% {freq_pos:<12.2f}% {status}")
        
        # Análise por posição dos TOP 5
        print(f"\n📍 Distribuição por Posição (TOP 5):")
        for dados in self.resultados['top_10_puxados'][:5]:
            num = dados['numero']
            posicoes = dados['aparicoes_por_posicao']
            
            if posicoes:
                posicoes_str = ', '.join([f"+{pos}:{qtd}x" for pos, qtd in sorted(posicoes.items())])
                print(f"   Número {num}: {posicoes_str}")
        
        # Estatísticas gerais
        print(f"\n📊 Estatísticas dos TOP 10:")
        top_lifts = [d['lift'] for d in self.resultados['top_10_puxados']]
        top_probs = [d['prob_aparecer'] for d in self.resultados['top_10_puxados']]
        
        print(f"   Lift médio: {sum(top_lifts)/len(top_lifts):.2f}x")
        print(f"   Prob média de aparecer: {sum(top_probs)/len(top_probs):.1f}%")
        print(f"   Maior lift: {max(top_lifts):.2f}x (#{self.resultados['top_10_puxados'][0]['numero']})")
        
        # Conclusão
        print(f"\n💡 Conclusão:")
        muito_fortes = [d['numero'] for d in self.resultados['top_10_puxados'] if d['lift'] >= 2.0]
        fortes = [d['numero'] for d in self.resultados['top_10_puxados'] if 1.5 <= d['lift'] < 2.0]
        
        if muito_fortes:
            print(f"   🔥🔥 Correlação MUITO FORTE (lift ≥ 2.0x): {muito_fortes}")
        if fortes:
            print(f"   🔥 Correlação FORTE (lift ≥ 1.5x): {fortes}")
        
        # Lista final recomendada
        recomendados = [d['numero'] for d in self.resultados['top_10_puxados'] if d['lift'] >= 1.2]
        if recomendados:
            print(f"\n✅ LISTA RECOMENDADA (lift ≥ 1.2x):")
            print(f"   {recomendados}")
        
        print("\n" + "="*90)
    
    def salvar_json(self, filename: str = "analise_puxadas_auto.json"):
        """Salva resultados em JSON"""
        resultado_serializavel = {
            'numero_gatilho': self.resultados['numero_gatilho'],
            'janela_forward': self.resultados['janela_forward'],
            'janela_lookback': self.resultados['janela_lookback'],
            'total_ocorrencias_gatilho': self.resultados['total_ocorrencias_gatilho'],
            'total_jogadas_analisadas': self.resultados['total_jogadas_analisadas'],
            'filtros': {
                'min_ocorrencias': MIN_OCORRENCIAS,
                'min_lift': MIN_LIFT
            },
            'top_10_puxados': self.resultados['top_10_puxados'],
            'todos_numeros': self.resultados['puxadas_por_numero'],
            'distribuicao_por_posicao': {
                pos: dict(counter) 
                for pos, counter in self.resultados['distribuicao_por_posicao'].items()
            },
            'timestamp_analise': datetime.now().isoformat()
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(resultado_serializavel, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Resultados salvos em: {filename}")


async def main():
    """Função principal"""
    print("🎯 Descoberta Automática de Números Puxados")
    print("="*90)
    
    # Conecta ao MongoDB
    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[MONGODB_DATABASE]
    
    print(f"🔌 Conectado ao MongoDB: {MONGODB_DATABASE}")
    
    # Cria analisador
    analisador = AnalisadorPuxadasAuto(db, MONGODB_COLLECTION)
    
    # Busca histórico
    historico = await analisador.buscar_historico(ROULETTE_ID, LIMITE_HISTORICO)
    
    if len(historico) < 100:
        print("❌ Histórico insuficiente para análise!")
        return
    
    # Analisa puxadas
    analisador.analisar_puxadas(historico)
    
    # Exibe relatório
    analisador.exibir_relatorio()
    
    # Salva JSON
    analisador.salvar_json()
    
    # Fecha conexão
    client.close()
    print("\n✅ Análise concluída!")


if __name__ == "__main__":
    asyncio.run(main())