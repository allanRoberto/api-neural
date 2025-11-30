import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import pytz

from patterns.base import BasePattern, PatternResult
from core.db import history_coll
from helpers.utils.filters import get_neighbords, get_mirror


class TemporalPattern(BasePattern):
    """
    Padrão Temporal com score real (alinhado com o Estelar)
    """

    def __init__(
        self,
        interval_minutes: int = 2,
        days_back: int = 30,
        minute_offset: int = 0,
        roulette_id: str = "pragmatic-brazilian-roulette",
    ):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        self.interval_minutes = interval_minutes
        self.days_back = days_back
        self.minute_offset = minute_offset
        self.roulette_id = roulette_id

        self.W_NUM = 0.3
        self.W_NEIGHBOR = 0.25
        self.W_MIRROR = 0.18

        self._cache = {}
        self._cache_timestamp = None
        self._cache_duration_seconds = 180  # 3 minutos

    def _should_update_cache(self) -> bool:
        if self._cache_timestamp is None:
            return True
        return (datetime.now() - self._cache_timestamp).total_seconds() > self._cache_duration_seconds

    def _get_current_time_br(self) -> str:
        tz_br = pytz.timezone("America/Sao_Paulo")
        now_br = datetime.now(tz_br) + timedelta(minutes=self.minute_offset)
        return now_br.strftime("%H:%M")

    async def _fetch_temporal_data(
        self,
        roulette_id: str,
        time_str: str,
        interval: int,
        days_back: int
    ) -> Optional[List[int]]:

        try:
            hour, minute = map(int, time_str.split(":"))

            start_min = minute - interval
            end_min = minute + interval
            end_hour = hour

            if end_min >= 60:
                end_hour = (hour + 1) % 24
                end_min = end_min % 60

            start_date = datetime.now() - timedelta(days=days_back)

            filter_query = {
                "roulette_id": roulette_id,
                "timestamp": {"$gte": start_date}
            }

            cursor = history_coll.find(filter_query)
            results = await cursor.to_list(length=None)

            tz_br = pytz.timezone("America/Sao_Paulo")
            numbers = []

            for doc in results:
                ts = doc["timestamp"]
                if ts.tzinfo is None:
                    ts = pytz.utc.localize(ts)
                br_time = ts.astimezone(tz_br)

                h = br_time.hour
                m = br_time.minute

                is_in = False

                if hour == end_hour:
                    if h == hour and start_min <= m < end_min:
                        is_in = True
                else:
                    if (h == hour and m >= start_min) or (h == end_hour and m < end_min):
                        is_in = True

                if is_in:
                    numbers.append(doc["value"])

            return numbers

        except Exception as e:
            self.logger.error(f"Erro no fetch temporal: {e}", exc_info=True)
            return None

    def _score_temporal(self, nums: List[int]) -> Dict[int, float]:
        """
        Score REAL do temporal (modelo igual ao Estelar)
        """

        scores = {}

        for num in nums:
            # Número base
            scores[num] = scores.get(num, 0.0) + self.W_NUM

            # Vizinhos
            for viz in get_neighbords(num):
                if 0 <= viz <= 36:
                    scores[viz] = scores.get(viz, 0.0) + self.W_NEIGHBOR

            # Espelhos
            mirrors = get_mirror(num)
            if isinstance(mirrors, int):
                mirrors = [mirrors]
            for esp in mirrors:
                if 0 <= esp <= 36:
                    scores[esp] = scores.get(esp, 0.0) + self.W_MIRROR

        return self.normalize_scores(scores)

    async def analyze(
        self,
        history: List[int],
        target_time: str = None,
        **kwargs
    ) -> PatternResult:

        roulette_id = kwargs.get("roulette_id", self.roulette_id)
        interval_minutes = kwargs.get("interval_minutes", self.interval_minutes)
        days_back = kwargs.get("days_back", self.days_back)

        time_str = target_time or self._get_current_time_br()

        # CACHE
        cache_key = f"{roulette_id}_{time_str}_{interval_minutes}_{days_back}"
        if cache_key in self._cache and not self._should_update_cache():
            nums = self._cache[cache_key]
        else:
            nums = await self._fetch_temporal_data(
                roulette_id,
                time_str,
                interval_minutes,
                days_back,
            )
            self._cache[cache_key] = nums
            self._cache_timestamp = datetime.now()

        if not nums:
            return PatternResult(
                candidatos=[],
                scores={},
                metadata={
                    "error": "Sem dados suficientes",
                    "roulette_id": roulette_id,
                    "time_analyzed": time_str
                },
                pattern_name="TEMPORAL"
            )

        # SCORE REAL (não frequência simples)
        scores = self._score_temporal(nums)

        # Candidatos = top-N (máximo 20)
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        candidatos = [n for n, s in top[:12]]

        metadata = {
            "roulette_id": roulette_id,
            "time_analyzed": time_str,
            "interval_minutes": interval_minutes,
            "days_back": days_back,
            "total_numbers_found": len(nums),
            "unique_numbers": len(set(nums)),
            "top_raw": top[:10],
        }

        return PatternResult(
            candidatos=candidatos[:12],
            scores=scores,
            metadata=metadata,
            pattern_name="TEMPORAL"
        )