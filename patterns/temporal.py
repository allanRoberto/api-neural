"""
Padrão TEMPORAL - Análise de frequência temporal
Analisa quais números tendem a aparecer em horários específicos baseado no histórico
"""

import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
import pytz

from patterns.base import BasePattern

# IMPORTS ESPECÍFICOS DO SEU PROJETO
# Ajuste o caminho de history_coll e helpers conforme estão no seu repo.
from core.db import history_coll  # <-- ajuste se necessário
from helpers.utils.filters import (
    get_neighbords,
    get_mirror
)


class TemporalPattern(BasePattern):
    """
    Padrão que analisa a frequência temporal dos números.
    
    Usa dados históricos para identificar quais números tendem a aparecer
    em determinados horários, baseado na média dos últimos N dias.
    
    ADAPTAÇÃO:
    - Não usa mais API HTTP (aiohttp).
    - Busca diretamente no MongoDB via history_coll, usando a mesma lógica
      da função get_prediction_detail.
    - O horário pode ser definido automaticamente com base no horário atual
      de Brasília + um offset em minutos (ex.: -5, +3), configurável.
    """
    
    def __init__(
        self,
        interval_minutes: int = 5,
        days_back: int = 30,
        min_occurrences: int = 3,
        roulette_id: str = "pragmatic-brazilian-roulette",
        minute_offset: int = 0,  # offset em minutos em relação ao horário atual
    ):
        """
        Inicializa o padrão temporal.
        
        Args:
            interval_minutes: Intervalo em minutos para análise (1, 5, 10, 15, 20, 30)
            days_back: Quantos dias para trás analisar
            min_occurrences: Mínimo de ocorrências para considerar um número relevante
            roulette_id: ID da roleta a ser analisada
            minute_offset: Offset em minutos em relação ao horário atual de Brasília.
                           Ex.: -5 (5 minutos antes), +3 (3 minutos depois).
        """
        super().__init__()
        self.logger = logging.getLogger(__name__)

        self.interval_minutes = interval_minutes
        self.days_back = days_back
        self.min_occurrences = min_occurrences
        self.roulette_id = roulette_id
        self.minute_offset = minute_offset
        
        # Cache para evitar recomputar tudo a cada chamada
        self._cache: Dict[str, Dict] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_duration_seconds = 300  # 5 minutos de cache
    
    def _should_update_cache(self) -> bool:
        """Verifica se o cache deve ser atualizado."""
        if self._cache_timestamp is None:
            return True
        
        elapsed = (datetime.now() - self._cache_timestamp).total_seconds()
        return elapsed >= self._cache_duration_seconds
    
    def _get_current_time_br(self, minute_offset: int = 0) -> str:
        """
        Retorna o horário atual no fuso horário de Brasília no formato HH:MM,
        aplicando um offset em minutos.
        """
        tz_br = pytz.timezone("America/Sao_Paulo")
        now_br = datetime.now(tz_br) + timedelta(minutes=minute_offset)

        print(now_br, "horario agora!!!!!!!")
        return now_br.strftime("%H:%M")

    async def _compute_temporal_data(
        self,
        roulette_id: str,
        time_str: str,
        interval: int,
        days_back: int,
    ) -> Optional[Dict]:
        """
        Implementa a lógica da função get_prediction_detail diretamente,
        sem passar por HTTP, usando history_coll.

        Args:
            roulette_id: ID da roleta
            time_str: horário no formato HH:MM
            interval: intervalo em minutos
            days_back: quantos dias anteriores analisar

        Returns:
            Dicionário com a análise temporal (ranking, estatísticas, etc.)
        """
        try:
            # Pesos (ajuste como quiser)
            WEIGHT_BASE = 3        # peso do próprio número
            WEIGHT_NEIGHBOR = 2.5  # peso dos vizinhos
            WEIGHT_MIRROR = 2.9    # peso dos espelhos

            # Parse do horário
            hour, minute = map(int, time_str.split(":"))
            
            # Calcular início e fim do intervalo (simples, em torno do minuto)
            start_minute = minute - interval
            end_minute = minute + interval
            end_hour = hour

            if end_minute >= 60:
                end_hour = (hour + 1) % 24
                end_minute = end_minute % 60

            # Buscar dados históricos
            start_date = datetime.now() - timedelta(days=days_back)
            filter_query = {
                "roulette_id": roulette_id,
                "timestamp": {"$gte": start_date}
            }
            
            cursor = history_coll.find(filter_query)
            results = await cursor.to_list(length=None)
            
            tz_br = pytz.timezone("America/Sao_Paulo")
            
            # Contadores
            numbers_count: Dict[int, int] = {}
            weighted_scores: Dict[int, float] = {}
            total_in_interval = 0
            days_with_data = set()
            
            # Contadores para análises adicionais
            colors_count = {"verde": 0, "vermelho": 0, "preto": 0}
            dozens_count = {"1ª dúzia": 0, "2ª dúzia": 0, "3ª dúzia": 0, "zero": 0}
            columns_count = {"1ª coluna": 0, "2ª coluna": 0, "3ª coluna": 0, "zero": 0}
            parity_count = {"par": 0, "ímpar": 0, "zero": 0}
            half_count = {"1-18": 0, "19-36": 0, "zero": 0}
            
            for doc in results:
                timestamp = doc["timestamp"]
                if timestamp.tzinfo is None:
                    timestamp = pytz.utc.localize(timestamp)
                br_time = timestamp.astimezone(tz_br)
                
                # Verificar se está no intervalo
                doc_hour = br_time.hour
                doc_minute = br_time.minute
                
                in_interval = False
                
                # Caso simples: mesma hora
                if hour == end_hour:
                    if doc_hour == hour and start_minute <= doc_minute < end_minute:
                        in_interval = True
                # Caso complexo: atravessa hora seguinte
                else:
                    if (doc_hour == hour and doc_minute >= start_minute) or \
                       (doc_hour == end_hour and doc_minute < end_minute):
                        in_interval = True
                
                if not in_interval:
                    continue

                number = doc["value"]

                # Contagem simples
                if number not in numbers_count:
                    numbers_count[number] = 0
                numbers_count[number] += 1
                total_in_interval += 1
                days_with_data.add(br_time.date())

                # -------------------------
                # PONTUAÇÃO PONDERADA
                # -------------------------
                if number not in weighted_scores:
                    weighted_scores[number] = 0.0

                # 1) peso do próprio número
                weighted_scores[number] += WEIGHT_BASE

                # 2) peso dos vizinhos
                try:
                    neighbors = get_neighbords(number)  # deve retornar lista de ints
                except NameError:
                    neighbors = []  # fallback se não estiver importado
                for n in neighbors:
                    if n < 0 or n > 36:
                        continue
                    if n not in weighted_scores:
                        weighted_scores[n] = 0.0
                    weighted_scores[n] += WEIGHT_NEIGHBOR

                # 3) peso dos espelhos
                try:
                    mirrors = get_mirror(number)  # deve retornar lista de ints ou um int
                except NameError:
                    mirrors = []
                if isinstance(mirrors, int):
                    mirrors = [mirrors]
                for m in mirrors:
                    if m < 0 or m > 36:
                        continue
                    if m not in weighted_scores:
                        weighted_scores[m] = 0.0
                    weighted_scores[m] += WEIGHT_MIRROR

                # -------------------------
                # Análises auxiliares (cor, dúzia, coluna, etc.)
                # -------------------------
                if number == 0:
                    colors_count["verde"] += 1
                    dozens_count["zero"] += 1
                    columns_count["zero"] += 1
                    parity_count["zero"] += 1
                    half_count["zero"] += 1
                else:
                    # Cores
                    red_numbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
                    if number in red_numbers:
                        colors_count["vermelho"] += 1
                    else:
                        colors_count["preto"] += 1
                    
                    # Dúzias
                    if 1 <= number <= 12:
                        dozens_count["1ª dúzia"] += 1
                    elif 13 <= number <= 24:
                        dozens_count["2ª dúzia"] += 1
                    elif 25 <= number <= 36:
                        dozens_count["3ª dúzia"] += 1
                    
                    # Colunas
                    if number % 3 == 1:
                        columns_count["1ª coluna"] += 1
                    elif number % 3 == 2:
                        columns_count["2ª coluna"] += 1
                    elif number % 3 == 0:
                        columns_count["3ª coluna"] += 1
                    
                    # Paridade
                    if number % 2 == 0:
                        parity_count["par"] += 1
                    else:
                        parity_count["ímpar"] += 1
                    
                    # Metades
                    if number <= 18:
                        half_count["1-18"] += 1
                    else:
                        half_count["19-36"] += 1
            
            # Criar ranking ponderado
            ranking = []
            existing_days = len(days_with_data) if days_with_data else 0

            for num in range(37):
                count = numbers_count.get(num, 0)
                weighted_score = weighted_scores.get(num, 0.0)
                percentage = (count / total_in_interval * 100) if total_in_interval > 0 else 0.0
                avg_per_day = (count / existing_days) if existing_days > 0 else 0.0

                ranking.append({
                    "number": num,
                    "count": count,
                    "percentage": percentage,
                    "average_per_day": avg_per_day,
                    "weighted_score": weighted_score
                })
            
            # Ordenar por score ponderado (desc)
            ranking.sort(key=lambda x: x["weighted_score"], reverse=True)

            # Calcular porcentagens para análises adicionais
            def calc_percentage(count: int) -> float:
                return (count / total_in_interval * 100) if total_in_interval > 0 else 0.0
            
            colors_analysis = {
                color: {
                    "count": count,
                    "percentage": calc_percentage(count)
                }
                for color, count in colors_count.items()
            }
            
            
            parity_analysis = {
                parity: {
                    "count": count,
                    "percentage": calc_percentage(count)
                }
                for parity, count in parity_count.items()
            }
            
            half_analysis = {
                half: {
                    "count": count,
                    "percentage": calc_percentage(count)
                }
                for half, count in half_count.items()
            }
            
            return {
                "time": time_str,
                "interval_minutes": interval,
                "interval_end": f"{end_hour:02d}:{end_minute:02d}",
                "days_analyzed": days_back,
                "total_occurrences_in_interval": total_in_interval,
                "days_with_occurrences": existing_days,
                "ranking": ranking,
                "top_5": ranking[:36],
                "bottom_5": list(sorted(ranking, key=lambda x: x["weighted_score"]))[:5],
                "colors": colors_analysis,
                
                "parity": parity_analysis,
                "half": half_analysis
            }
        
        except Exception as e:
            self.logger.error(f"Erro na previsão temporal (compute): {e}", exc_info=True)
            return None
    
    def _convert_ranking_to_candidates(self, ranking: List[Dict]) -> Dict[int, float]:
        """
        Converte o ranking em candidatos com scores normalizados.
        
        Args:
            ranking: Lista de dicionários com 'number', 'count', 'percentage', etc.
            
        Returns:
            Dicionário {número: score}
        """
        candidates: Dict[int, float] = {}
        
        # Filtrar números com ocorrências mínimas
        valid_numbers = [
            item for item in ranking 
            if item['count'] >= self.min_occurrences
        ]
        
        if not valid_numbers:
            self.logger.warning("No numbers meet minimum occurrence threshold")
            return candidates
        
        # Normalizar scores baseado na frequência
        max_count = max(item['count'] for item in valid_numbers)
        
        for item in valid_numbers:
            number = item['number']
            count = item['count']
            
            # Score baseado na frequência normalizada
            # Números com maior frequência histórica = maior score
            score = (count / max_count) * 100
            
            # Bônus para números muito consistentes (aparecem em muitos dias)
            avg_per_day = item.get('average_per_day', 0)
            if avg_per_day >= 1.0:
                score *= 1.2
            elif avg_per_day >= 0.5:
                score *= 1.1
            
            candidates[number] = score
        
        self.logger.info(f"Temporal pattern found {len(candidates)} candidates")
        return candidates
    
    async def analyze(
        self,
        history: List[int],
        target_time: str = None,
        **kwargs
    ) -> Tuple[Dict[int, float], Dict]:
        """
        Analisa o padrão temporal e retorna candidatos.
        
        Args:
            history: Histórico de números (não usado diretamente, mas mantido por compatibilidade)
            target_time: Horário específico para análise (formato HH:MM).
                         Se None, usa horário atual de Brasília + minute_offset.
            **kwargs: Parâmetros adicionais (roulette_id, interval_minutes, days_back, minute_offset)
            
        Returns:
            Tupla (candidatos, metadata)
        """
        # Permitir override de parâmetros via kwargs
        roulette_id = kwargs.get('roulette_id', self.roulette_id)
        interval_minutes = kwargs.get('interval_minutes', self.interval_minutes)
        days_back = kwargs.get('days_back', self.days_back)
        minute_offset = kwargs.get('minute_offset', self.minute_offset)
        
        # Atualizar parâmetros se fornecidos
        if roulette_id != self.roulette_id:
            self.roulette_id = roulette_id
        if interval_minutes != self.interval_minutes:
            self.interval_minutes = interval_minutes
        if days_back != self.days_back:
            self.days_back = days_back
        if minute_offset != self.minute_offset:
            self.minute_offset = minute_offset
        
        
        time_str = self._get_current_time_br(self.minute_offset)
        
        # Verificar cache
        cache_key = f"{roulette_id}_{time_str}_{interval_minutes}_{days_back}"
        if cache_key in self._cache and not self._should_update_cache():
            self.logger.info("Using cached temporal data")
            temporal_data = self._cache[cache_key]
        else:
            # Buscar dados diretamente no MongoDB (sem API)
            temporal_data = await self._compute_temporal_data(
                roulette_id=roulette_id,
                time_str=time_str,
                interval=interval_minutes,
                days_back=days_back,
            )
            if temporal_data:
                self._cache[cache_key] = temporal_data
                self._cache_timestamp = datetime.now()
            else:
                self.logger.warning("Failed to compute temporal data, returning empty candidates")
                return {}, {
                    "error": "Failed to compute temporal data",
                    "time_analyzed": time_str,
                    "roulette_id": roulette_id,
                }
        
        # Converter ranking em candidatos
        ranking = temporal_data.get('ranking', [])
        candidates = self._convert_ranking_to_candidates(ranking)
        
        # Metadata para debugging e transparência
        metadata = {
            "time_analyzed": time_str,
            "interval_minutes": interval_minutes,
            "interval_end": temporal_data.get('interval_end', ''),
            "days_analyzed": days_back,
            "total_occurrences": temporal_data.get('total_occurrences_in_interval', 0),
            "days_with_data": temporal_data.get('days_with_occurrences', 0),
            "candidates_found": len(candidates),
            "top_5_historical": temporal_data.get('top_5', []),
            "roulette_id": roulette_id,
            "minute_offset": self.minute_offset,
        }
        
        return candidates, metadata
    
    def get_name(self) -> str:
        """Retorna o nome do padrão."""
        return "TEMPORAL"
    
    def get_description(self) -> str:
        """Retorna a descrição do padrão."""
        return (
            f"Análise de frequência temporal: identifica números que tendem a aparecer "
            f"em horários específicos baseado nos últimos {self.days_back} dias "
            f"(intervalo de {self.interval_minutes} minutos, offset {self.minute_offset} min)"
        )


# Função auxiliar para criar instância com configuração padrão
def create_temporal_pattern(**kwargs) -> TemporalPattern:
    """
    Cria uma instância do TemporalPattern com configuração padrão.
    
    Args:
        **kwargs: Parâmetros opcionais para override
        
    Returns:
        Instância configurada do TemporalPattern
    """
    return TemporalPattern(**kwargs)
