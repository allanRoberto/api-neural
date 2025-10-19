"""
tests/test_assertividade.py

Sistema de Testes de Assertividade - Backtesting com dados reais

Mede a performance do padrão MASTER usando dados históricos do MongoDB
"""

import sys
import os
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict, field
import argparse

# Adicionar path do projeto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import Settings
from patterns.master import MasterPattern




@dataclass
class TestResult:
    janela_id: Optional[int] = None
    historico_size: Optional[int] = None
    sugestoes: List[int] = field(default_factory=list)
    numero_real: Optional[int] = None
    acertou: Optional[bool] = None
    posicao_acerto: Optional[int] = None
    tempo_ate_acerto: Optional[int] = None
    modo_master: Optional[str] = None
    acertos_por_posicao: Dict[int, int] = field(default_factory=dict)
    contexto: Dict[str, Any] = field(default_factory=dict)
    tempo_moda_acerto: Optional[int] = None
    # campos que o seu código já passa em alguns pontos:
    teste_id: Optional[int] = None
    posicao_sugestao: Optional[int] = None
    proximos_numeros: Optional[int] = None
    numero_acertado: Optional[int] = None
    giro_acerto: Optional[int] = None


@dataclass
class RelatorioCompleto:
    """Relatório completo de todos os testes"""
    roulette_id: str
    timestamp: str
    total_testes: int
    giros_verificados: int
    config_master: Dict
    
    # Resultados
    testes: List[TestResult]
    total_acertos: int
    total_erros: int
    
    # Métricas por tempo
    acertos_por_giro: Dict[int, int]  # {giro: quantidade_acertos}
    taxa_acerto_acumulada: Dict[int, float]  # {até_giro_N: taxa}
    
    # Estatísticas
    tempo_medio_acerto: Optional[float] = None
    tempo_mediano_acerto: Optional[int] = None
    tempo_moda_acerto: Optional[int] = None
    
    # Por posição
    acertos_por_posicao: Dict[int, int] = field(default_factory=dict)  # {posicao: quantidade}
    
    # Números
    numeros_mais_sugeridos: List[Tuple[int, int]] = field(default_factory=list)  # [(numero, vezes)]
    numeros_mais_acertados: List[Tuple[int, int]] = field(default_factory=list)  # [(numero, vezes)]


class TestadorAssertividade:
    """
    Classe principal para testar assertividade dos padrões
    """
    
    def __init__(self, config: Dict = None):
        """
        Inicializa o testador
        
        Args:
            config: Configurações do teste
        """
        self.config = config or {}
        self.settings = Settings()
        self.client = None
        self.db = None
        
        # Configurações padrão
        self.total_numeros = self.config.get('total_numeros', 50000)
        self.tamanho_historico = self.config.get('tamanho_historico', 45000)
        self.tamanho_verificacao = self.config.get('tamanho_verificacao', 60)
        self.quantidade_testes = self.config.get('quantidade_testes', 100)
        self.offset_janela = self.config.get('offset_janela', 50)
        self.quantidade_sugestoes = self.config.get('quantidade_sugestoes', 6)
        
        # Config do MASTER
        self.master_config = self.config.get('master_config', {
            'janela_min': 2,
            'janela_max': 4,
            'min_support': 2
        })
    
    async def conectar_mongodb(self):
        """Conecta ao MongoDB"""
        try:
            self.client = AsyncIOMotorClient(self.settings.mongodb_url)
            self.db = self.client[self.settings.MONGODB_DATABASE]
            await self.client.admin.command('ping')
            print(f"✅ Conectado ao MongoDB: {self.settings.MONGODB_DATABASE}")
        except Exception as e:
            print(f"❌ Erro ao conectar MongoDB: {e}")
            raise
    
    async def desconectar_mongodb(self):
        """Desconecta do MongoDB"""
        if self.client:
            self.client.close()
    
    async def buscar_historico(self, roulette_id: str, limit: int) -> List[int]:
        """
        Busca histórico de uma roleta
        
        Args:
            roulette_id: ID da roleta
            limit: Quantidade de números
        
        Returns:
            Lista de números (mais recente primeiro)
        """
        collection = self.db[self.settings.MONGODB_COLLECTION]
        
        cursor = collection.find(
            {"roulette_id": roulette_id}
        ).sort("timestamp", -1).limit(limit)
        
        documents = await cursor.to_list(length=limit)
        numeros = [doc.get("value", 0) for doc in documents]
        
        return numeros
    
    def simular_previsao(
        self,
        historico: List[int],
        master: MasterPattern
    ) -> List[int]:
        """
        Simula uma previsão usando o histórico
        
        Args:
            historico: Números para análise
            master: Instância do MasterPattern
        
        Returns:
            Lista de sugestões (TOP N)
        """
        resultado = master.analyze(historico)
        top_sugestoes = resultado.get_top_n(self.quantidade_sugestoes)
        return [num for num, score in top_sugestoes]
    
    def verificar_acerto(
        self,
        sugestoes: List[int],
        proximos: List[int]
    ) -> Tuple[bool, Optional[int], Optional[int], Optional[int]]:
        """
        Verifica se alguma sugestão acertou nos próximos números
        
        Args:
            sugestoes: Lista de números sugeridos
            proximos: Lista de próximos números reais
        
        Returns:
            (acertou, numero_acertado, giro_acerto, posicao_sugestao)
        """
        for giro_idx, numero_real in enumerate(proximos, start=1):
            if numero_real in sugestoes:
                posicao = sugestoes.index(numero_real) + 1
                return True, numero_real, giro_idx, posicao
        
        return False, None, None, None
    
    async def executar_backtesting(
        self,
        roulette_id: str
    ) -> RelatorioCompleto:
        """
        Executa backtesting completo em uma roleta
        
        Args:
            roulette_id: ID da roleta
        
        Returns:
            Relatório completo
        """
        print(f"\n🎯 Iniciando backtesting: {roulette_id}")
        print(f"   Testes: {self.quantidade_testes}")
        print(f"   Verificando até: {self.tamanho_verificacao} giros")
        print(f"   Sugestões: {self.quantidade_sugestoes} números\n")
        
        # Buscar dados
        print("📊 Buscando histórico do MongoDB...")
        historico_completo = await self.buscar_historico(
            roulette_id,
            self.total_numeros
        )
        
        if len(historico_completo) < self.tamanho_historico + self.tamanho_verificacao:
            raise ValueError(
                f"Histórico insuficiente: {len(historico_completo)} números "
                f"(necessário: {self.tamanho_historico + self.tamanho_verificacao})"
            )
        
        print(f"✅ {len(historico_completo)} números carregados\n")
        
        # Criar instância do MASTER
        master = MasterPattern(config=self.master_config)
        
        # Executar testes
        print("🔄 Executando testes...")
        resultados = []
        
        for teste_id in range(1, self.quantidade_testes + 1):
            # Calcular índice inicial da janela
            idx_inicio = (teste_id - 1) * self.offset_janela
            idx_fim_analise = idx_inicio + self.tamanho_historico
            idx_fim_verificacao = idx_fim_analise + self.tamanho_verificacao
            
            # Verificar se há dados suficientes
            if idx_fim_verificacao > len(historico_completo):
                print(f"⚠️  Teste #{teste_id}: Dados insuficientes, parando")
                break
            
            # Extrair janelas
            historico_analise = historico_completo[idx_inicio:idx_fim_analise]
            proximos_numeros = historico_completo[idx_fim_analise:idx_fim_verificacao]
            
            # Gerar sugestões
            sugestoes = self.simular_previsao(historico_analise, master)
            
            # Verificar acerto
            acertou, numero, giro, posicao = self.verificar_acerto(
                sugestoes,
                proximos_numeros
            )
            
            # Armazenar resultado
            resultado = TestResult(
                teste_id=teste_id,
                sugestoes=sugestoes,
                proximos_numeros=proximos_numeros[:10],  # Guardar só os primeiros 10
                acertou=acertou,
                numero_acertado=numero,
                giro_acerto=giro,
                posicao_sugestao=posicao
            )
            resultados.append(resultado)
            
            # Progresso
            if teste_id % 10 == 0:
                acertos_ate_agora = sum(1 for r in resultados if r.acertou)
                taxa = (acertos_ate_agora / teste_id) * 100
                print(f"   Teste {teste_id}/{self.quantidade_testes} - Taxa: {taxa:.1f}%")
        
        print(f"\n✅ {len(resultados)} testes concluídos!\n")
        
        # Calcular métricas
        relatorio = self._calcular_metricas(roulette_id, resultados)
        
        return relatorio
    
    def _calcular_metricas(
        self,
        roulette_id: str,
        resultados: List[TestResult]
    ) -> RelatorioCompleto:
        """
        Calcula todas as métricas a partir dos resultados
        
        Args:
            roulette_id: ID da roleta
            resultados: Lista de resultados dos testes
        
        Returns:
            Relatório completo com métricas
        """
        total_testes = len(resultados)
        acertos = [r for r in resultados if r.acertou]
        total_acertos = len(acertos)
        total_erros = total_testes - total_acertos
        
        # Acertos por giro
        acertos_por_giro = Counter([r.giro_acerto for r in acertos])
        
        # Taxa acumulada
        taxa_acerto_acumulada = {}
        for giro in range(1, self.tamanho_verificacao + 1):
            acertos_ate_giro = sum(
                1 for r in acertos if r.giro_acerto <= giro
            )
            taxa_acerto_acumulada[giro] = (acertos_ate_giro / total_testes) * 100
        
        # Estatísticas de tempo
        tempos_acerto = [r.giro_acerto for r in acertos]
        tempo_medio = sum(tempos_acerto) / len(tempos_acerto) if tempos_acerto else None
        tempo_mediano = sorted(tempos_acerto)[len(tempos_acerto)//2] if tempos_acerto else None
        tempo_moda = Counter(tempos_acerto).most_common(1)[0][0] if tempos_acerto else None
        
        # Acertos por posição
        acertos_por_posicao = Counter([r.posicao_sugestao for r in acertos])
        
        # Números mais sugeridos
        todos_sugeridos = []
        for r in resultados:
            todos_sugeridos.extend(r.sugestoes)
        numeros_mais_sugeridos = Counter(todos_sugeridos).most_common(10)
        
        # Números mais acertados
        numeros_acertados = [r.numero_acertado for r in acertos]
        numeros_mais_acertados = Counter(numeros_acertados).most_common(10)
        
        return RelatorioCompleto(
            roulette_id=roulette_id,
            timestamp=datetime.now().isoformat(),
            total_testes=total_testes,
            giros_verificados=self.tamanho_verificacao,
            config_master=self.master_config,
            testes=resultados,
            total_acertos=total_acertos,
            total_erros=total_erros,
            acertos_por_giro=dict(acertos_por_giro),
            taxa_acerto_acumulada=taxa_acerto_acumulada,
            tempo_medio_acerto=tempo_medio,
            tempo_mediano_acerto=tempo_mediano,
            tempo_moda_acerto=tempo_moda,
            acertos_por_posicao=dict(acertos_por_posicao),
            numeros_mais_sugeridos=numeros_mais_sugeridos,
            numeros_mais_acertados=numeros_mais_acertados
        )
    
    def imprimir_relatorio(self, relatorio: RelatorioCompleto):
        """
        Imprime relatório formatado no terminal
        
        Args:
            relatorio: Relatório completo
        """
        print("=" * 65)
        print("RELATÓRIO DE ASSERTIVIDADE - PADRÃO MASTER")
        print("=" * 65)
        print()
        print(f"Roleta: {relatorio.roulette_id}")
        print(f"Data: {relatorio.timestamp[:19]}")
        print(f"Total de testes: {relatorio.total_testes}")
        print(f"Verificando acerto em até: {relatorio.giros_verificados} giros")
        print()
        
        # Taxa de acerto por tempo
        print("-" * 65)
        print("TAXA DE ACERTO POR TEMPO")
        print("-" * 65)
        
        giros_chave = [1, 3, 5, 10, 20, 30, relatorio.giros_verificados]
        for giro in giros_chave:
            if giro in relatorio.taxa_acerto_acumulada:
                taxa = relatorio.taxa_acerto_acumulada[giro]
                acertos = int((taxa / 100) * relatorio.total_testes)
                print(f"Acerto em até {giro:2d} giro(s): {taxa:5.1f}% ({acertos}/{relatorio.total_testes})")
        
        print(f"\nNão acertou ({relatorio.giros_verificados} giros): "
              f"{(relatorio.total_erros / relatorio.total_testes * 100):.1f}% "
              f"({relatorio.total_erros}/{relatorio.total_testes})")
        print()
        
        # Tempo médio até acerto
        if relatorio.tempo_medio_acerto:
            print("-" * 65)
            print("TEMPO MÉDIO ATÉ ACERTO")
            print("-" * 65)
            print(f"Média:   {relatorio.tempo_medio_acerto:.1f} giros")
            print(f"Mediana: {relatorio.tempo_mediano_acerto} giros")
            print(f"Moda:    {relatorio.tempo_moda_acerto} giros (mais comum)")
            
            # Mais rápido e mais lento
            acertos = [r for r in relatorio.testes if r.acertou]
            if acertos:
                mais_rapido = min(r.giro_acerto for r in acertos)
                mais_lento = max(r.giro_acerto for r in acertos)
                count_rapido = sum(1 for r in acertos if r.giro_acerto == mais_rapido)
                
                print(f"\nMais rápido: {mais_rapido} giro(s)  ({count_rapido} vezes)")
                print(f"Mais lento:  {mais_lento} giros")
            print()
        
        # Acerto por posição
        print("-" * 65)
        print("ACERTO POR POSIÇÃO (nas sugestões)")
        print("-" * 65)
        
        for pos in range(1, self.quantidade_sugestoes + 1):
            count = relatorio.acertos_por_posicao.get(pos, 0)
            taxa = (count / relatorio.total_testes) * 100
            print(f"TOP {pos} acertou: {taxa:5.1f}% ({count}/{relatorio.total_testes})")
        print()
        
        # Distribuição de quando acerta
        print("-" * 65)
        print("DISTRIBUIÇÃO DE QUANDO ACERTA")
        print("-" * 65)
        
        if relatorio.total_acertos > 0:
            faixas = [
                (1, 5, "Giros 1-5"),
                (6, 10, "Giros 6-10"),
                (11, 20, "Giros 11-20"),
                (21, 999, "Giros 21+")
            ]
            
            for inicio, fim, label in faixas:
                count = sum(
                    1 for r in relatorio.testes
                    if r.acertou and inicio <= r.giro_acerto <= fim
                )
                if count > 0:
                    pct = (count / relatorio.total_acertos) * 100
                    barra = "█" * int(pct / 5)
                    print(f"{label:15s} {pct:5.1f}% dos acertos {barra}")
        print()
        
        # Números mais sugeridos
        print("-" * 65)
        print("NÚMEROS MAIS SUGERIDOS")
        print("-" * 65)
        
        for i, (num, vezes) in enumerate(relatorio.numeros_mais_sugeridos[:10], 1):
            # Contar quantas vezes acertou
            acertos_num = sum(
                1 for r in relatorio.testes
                if r.acertou and r.numero_acertado == num
            )
            print(f"{i:2d}. Número {num:2d}: {vezes:3d} vezes (acertou {acertos_num}x)")
        print()
        
        # Exemplos de acertos
        print("-" * 65)
        print("EXEMPLOS DE ACERTOS")
        print("-" * 65)
        
        acertos_exemplo = [r for r in relatorio.testes if r.acertou][:5]
        for r in acertos_exemplo:
            sugs = ','.join(str(n) for n in r.sugestoes)
            print(f"Teste #{r.teste_id:3d}: Sugestões [{sugs}] → "
                  f"Acertou {r.numero_acertado} no giro {r.giro_acerto}")
        
        print()
        print("=" * 65)
    
    def salvar_json(self, relatorio: RelatorioCompleto, filename: str = None):
        """
        Salva relatório em JSON
        
        Args:
            relatorio: Relatório completo
            filename: Nome do arquivo (opcional)
        """
        if filename is None:
            os.makedirs('tests/resultados', exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tests/resultados/{relatorio.roulette_id}_{timestamp}.json"
        
        # Converter para dict (simplificado, sem todos os testes)
        data = {
            'roulette_id': relatorio.roulette_id,
            'timestamp': relatorio.timestamp,
            'total_testes': relatorio.total_testes,
            'giros_verificados': relatorio.giros_verificados,
            'config_master': relatorio.config_master,
            'resumo': {
                'total_acertos': relatorio.total_acertos,
                'total_erros': relatorio.total_erros,
                'taxa_acerto_global': (relatorio.total_acertos / relatorio.total_testes * 100),
                'tempo_medio_acerto': relatorio.tempo_medio_acerto,
                'tempo_mediano_acerto': relatorio.tempo_mediano_acerto,
            },
            'taxa_acerto_acumulada': {
                str(k): v for k, v in relatorio.taxa_acerto_acumulada.items()
                if k in [1, 3, 5, 10, 20, 30, 60]
            },
            'acertos_por_posicao': relatorio.acertos_por_posicao,
            'numeros_mais_sugeridos': relatorio.numeros_mais_sugeridos[:10],
            'numeros_mais_acertados': relatorio.numeros_mais_acertados[:10],
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Relatório salvo: {filename}")


async def main():
    """Função principal"""
    parser = argparse.ArgumentParser(description='Testar assertividade do padrão MASTER')
    
    parser.add_argument(
        '--mode',
        choices=['quick', 'normal', 'complete', 'optimize'],
        default='normal',
        help='Modo de execução'
    )
    
    parser.add_argument(
        '--roulette',
        type=str,
        help='ID da roleta específica'
    )
    
    parser.add_argument(
        '--tests',
        type=int,
        help='Quantidade de testes'
    )
    
    parser.add_argument(
        '--check-giros',
        type=int,
        help='Verificar acerto em até N giros'
    )
    
    parser.add_argument(
        '--sugestoes',
        type=int,
        help='Quantidade de sugestões'
    )
    
    parser.add_argument(
        '--save-json',
        action='store_true',
        help='Salvar resultado em JSON'
    )
    
    args = parser.parse_args()
    
    # Configuração baseada no modo
    if args.mode == 'quick':
        config = {
            'quantidade_testes': 10,
            'tamanho_verificacao': 30,
        }
    elif args.mode == 'normal':
        config = {
            'quantidade_testes': 100,
            'tamanho_verificacao': 60,
        }
    elif args.mode == 'complete':
        config = {
            'quantidade_testes': 100,
            'tamanho_verificacao': 60,
        }
    else:  # optimize
        config = {
            'quantidade_testes': 50,
            'tamanho_verificacao': 60,
        }
    
    # Sobrescrever com args
    if args.tests:
        config['quantidade_testes'] = args.tests
    if args.check_giros:
        config['tamanho_verificacao'] = args.check_giros
    if args.sugestoes:
        config['quantidade_sugestoes'] = args.sugestoes
    
    # Criar testador
    testador = TestadorAssertividade(config=config)
    
    try:
        # Conectar
        await testador.conectar_mongodb()
        
        # Determinar roletas a testar
        if args.roulette:
            roulettes = [args.roulette]
        elif args.mode == 'complete':
            # Buscar todas as roletas
            collection = testador.db[testador.settings.MONGODB_COLLECTION]
            roulettes = await collection.distinct("roulette_id")
            print(f"🎰 {len(roulettes)} roletas encontradas")
        else:
            # Padrão: primeira roleta disponível
            collection = testador.db[testador.settings.MONGODB_COLLECTION]
            roulettes = await collection.distinct("roulette_id")
            roulettes = [roulettes[0]] if roulettes else []
        
        if not roulettes:
            print("❌ Nenhuma roleta encontrada no banco de dados")
            return
        
        # Executar testes
        for roulette_id in roulettes:
            try:
                relatorio = await testador.executar_backtesting(roulette_id)
            except ValueError as e:
                print(f"⚠️ {e} — ignorando '{roulette_id}'.");  
                continue

            testador.imprimir_relatorio(relatorio)
                
            if args.save_json:
                testador.salvar_json(relatorio)
            
            if len(roulettes) > 1:
                print("\n" + "="*65 + "\n")
            
        
    finally:
        await testador.desconectar_mongodb()


if __name__ == "__main__":
    asyncio.run(main())