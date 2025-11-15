"""
routes/sugestao.py

Rota para sugestões com Ensemble MASTER + ESTELAR + CHAIN
Inclui proteções dinâmicas (espelhos, vizinhos, zero)
"""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Dict, Set
from collections import defaultdict
import logging

from patterns.puxadas import PuxadasPattern 
from patterns.master import PatternMaster
from patterns.estelar import PatternEstelar
from patterns.chain import ChainAnalyzer
from patterns.temporal import TemporalPattern

from collections import defaultdict
from typing import Dict, List, Iterable, Optional

from utils.constants import ESPELHOS
from utils.helpers import get_vizinhos, get_espelho
from fastapi.responses import  JSONResponse, HTMLResponse

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")



router = APIRouter()
logger = logging.getLogger(__name__)


async def _get_historico_interno(request: Request, roulette_id: str, limit: int = 500):
    """
    Função auxiliar para buscar histórico (reutilizável)
    
    Args:
        request: Request FastAPI
        roulette_id: ID da roleta
        limit: Quantidade de números
    
    Returns:
        Lista de números
    
    Raises:
        HTTPException: Se houver erro ou histórico insuficiente
    """
    try:
        db = request.app.state.db
        settings = request.app.state.settings
        collection = db[settings.MONGODB_COLLECTION]
        
        cursor = collection.find(
            {"roulette_id": roulette_id}
        ).sort("timestamp", -1).limit(limit)
        
        documents = await cursor.to_list(length=limit)
        
        if len(documents) < 10:
            raise HTTPException(
                status_code=400,
                detail=f"Histórico insuficiente: {len(documents)} números (mínimo 10)"
            )
        
        # Extrair números (campo 'value')
        numeros = [doc.get("value", 0) for doc in documents]
        
        return numeros
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao buscar histórico: {str(e)}"
        )

def calcular_ensemble(
    resultado_master,
    resultado_estelar,
    resultado_chain,
    resultado_temporal,  # NOVO: 5º padrão
    w_master: float = 0.20,
    w_estelar: float = 0.20,
    w_chain: float = 0.20,
    w_temporal: float = 0.20  # NOVO
) -> Dict[int, float]:
    """
    Combina scores dos 5 padrões com pesos configuráveis
    
    Args:
        resultado_master: PatternResult do MASTER
        resultado_estelar: PatternResult do ESTELAR
        resultado_chain: PatternResult do CHAIN
        resultado_puxadas: PatternResult do PUXADAS
        resultado_temporal: Tuple (candidates, metadata) do TEMPORAL
        w_master: Peso do MASTER (0-1)
        w_estelar: Peso do ESTELAR (0-1)
        w_chain: Peso do CHAIN (0-1)
        w_puxadas: Peso do PUXADAS (0-1)
        w_temporal: Peso do TEMPORAL (0-1)
    
    Returns:
        Dict {numero: score_combinado} normalizado
    """
    # Ajuste dinâmico de pesos
    padroes_chain = resultado_chain.metadata.get('total_cadeias_aprendidas', 0)
    
    # TEMPORAL retorna (candidates, metadata) - extrair
    temporal_candidates = resultado_temporal[0] if isinstance(resultado_temporal, tuple) else {}
    temporal_metadata = resultado_temporal[1] if isinstance(resultado_temporal, tuple) else {}
    temporal_candidatos = temporal_metadata.get('candidates_found', 0)
    
   
    # Normaliza pesos
    total_peso = w_master + w_estelar + w_chain + w_temporal
    w_master /= total_peso
    w_estelar /= total_peso
    w_chain /= total_peso
    w_temporal /= total_peso
    
    # Combina scores
    scores_combinados = defaultdict(float)
    
    # MASTER
    for num, score in resultado_master.scores.items():
        scores_combinados[num] += w_master * score
    
    # ESTELAR
    for num, score in resultado_estelar.scores.items():
        scores_combinados[num] += w_estelar * score
    
    # CHAIN
    for num, score in resultado_chain.scores.items():
        scores_combinados[num] += w_chain * score
    

    
    # TEMPORAL (usa candidates dict diretamente)
    for num, score in temporal_candidates.items():
        scores_combinados[num] += w_temporal * score
    
    # Normaliza resultado final
    if scores_combinados:
        max_score = max(scores_combinados.values())
        if max_score > 0:
            scores_combinados = {
                num: score / max_score
                for num, score in scores_combinados.items()
            }
    
    return dict(scores_combinados)



from collections import defaultdict
from typing import Dict, List, Iterable, Optional, Any

def calcular_ensemble_rank(
    sugestoes_master: Any,
    sugestoes_estelar: Any,
    sugestoes_chain: Any,
    sugestoes_temporal: Any,
    *,
    w_master: float = 0.20,
    w_estelar: float = 0.20,
    w_chain: float = 0.20,
    w_temporal: float = 0.20,
    vizinhos_k: int = 1,
    peso_numero: float = 1.0,
    peso_espelho: float = 0.9,
    peso_vizinho: float = 0.7,
    peso_vizinho_espelho: float = 0.6
) -> Dict[int, float]:
    """
    Ranking por números (sem scores de entrada).
    Para cada número sugerido em cada padrão:
      - base: +1.0
      - espelho(s): +0.9
      - vizinhos(base): +0.7
      - vizinhos(espelho): +0.6
    Aplica o peso do padrão em cada contribuição.
    Retorna {numero: pontuacao}.
    """

    # -------- helpers para extrair números de qualquer formato --------
    def _as_int_list(seq) -> List[int]:
        out = []
        for x in seq or []:
            try:
                xi = int(x)
                if 0 <= xi <= 36:
                    out.append(xi)
            except Exception:
                continue
        return out

    def _extract_numbers(obj: Any) -> List[int]:
        """
        Aceita:
        - list/iterable de ints
        - dict {numero: score/...} -> usa keys
        - tuple (candidates, metadata) -> se candidates for dict/list
        - PatternResult-like:
            .numbers (list[int])
            .scores (dict[int->float]) -> usa keys com score>0
            .candidates (dict/list)
            .ranking (list[dict{number:..}]) -> pega 'number'
            .top_numbers / .bet_numbers (list[int])
        """
        if obj is None:
            return []

        # tuple (temporal: (candidates, metadata))
        if isinstance(obj, tuple) and len(obj) >= 1:
            cand = obj[0]
            if isinstance(cand, dict):
                return _as_int_list(cand.keys())
            if isinstance(cand, (list, tuple, set)):
                return _as_int_list(cand)

        # dict -> keys
        if isinstance(obj, dict):
            return _as_int_list(obj.keys())

        # iterable "puro"
        try:
            # strings não contam como iterável aqui
            if not isinstance(obj, (str, bytes)):
                it = iter(obj)  # pode lançar TypeError
                return _as_int_list(it)
        except TypeError:
            pass

        # objetos com atributos conhecidos (PatternResult etc.)
        for attr in ("top_numbers", "bet_numbers", "numbers"):
            if hasattr(obj, attr):
                return _as_int_list(getattr(obj, attr))

        if hasattr(obj, "scores"):
            try:
                sc = getattr(obj, "scores")
                if isinstance(sc, dict):
                    # pega só chaves com score > 0
                    return _as_int_list([k for k, v in sc.items() if (isinstance(v, (int, float)) and v > 0)])
            except Exception:
                pass

        if hasattr(obj, "candidates"):
            cand = getattr(obj, "candidates")
            if isinstance(cand, dict):
                return _as_int_list(cand.keys())
            if isinstance(cand, (list, tuple, set)):
                return _as_int_list(cand)

        if hasattr(obj, "ranking"):
            rk = getattr(obj, "ranking")
            # ranking pode ser list[dict{number:..}]
            try:
                nums = []
                for item in rk or []:
                    if isinstance(item, dict) and "number" in item:
                        nums.append(item["number"])
                if nums:
                    return _as_int_list(nums)
            except Exception:
                pass

        return []

    # -------- vizinhos / espelhos (usa suas funções; fallback silencioso) --------
    def _get_vizinhos(n: int) -> List[int]:
        try:
            v = get_vizinhos(n)  # sua função
            return _as_int_list(set(v))
        except Exception:
            return []

    def _get_vizinhos_k(n: int, k: int) -> List[int]:
        if k <= 1:
            return _get_vizinhos(n)
        fronteira = set([n])
        visitados = set([n])
        for _ in range(k):
            novos = set()
            for x in list(fronteira):
                for nb in _get_vizinhos(x):
                    if nb not in visitados:
                        novos.add(nb)
                        visitados.add(nb)
            fronteira = novos
        visitados.discard(n)
        return _as_int_list(visitados)

    def _get_espelhos(n: int) -> List[int]:
        try:
            m = get_espelho(n)  # sua função
            if isinstance(m, int):
                m = [m]
            return _as_int_list(set(m or []))
        except Exception:
            return []

    # -------- acumulação ponderada --------
    ranking: Dict[int, float] = defaultdict(float)

    def _acumula(nums: List[int], peso_padrao: float) -> None:
        if not nums:
            return
        vistos = set()
        for n in nums:
            if n in vistos:
                continue
            vistos.add(n)

            ranking[n] += peso_numero * peso_padrao

            espelhos = _get_espelhos(n)
            for me in espelhos:
                ranking[me] += peso_espelho * peso_padrao

            for nb in _get_vizinhos_k(n, vizinhos_k):
                ranking[nb] += peso_vizinho * peso_padrao

            for me in espelhos:
                for nbm in _get_vizinhos_k(me, vizinhos_k):
                    ranking[nbm] += peso_vizinho_espelho * peso_padrao

    _acumula(_extract_numbers(sugestoes_master),   w_master)
    _acumula(_extract_numbers(sugestoes_estelar),  w_estelar)
    _acumula(_extract_numbers(sugestoes_chain),    w_chain)
    _acumula(_extract_numbers(sugestoes_temporal), w_temporal)

    return dict(ranking)


def aplicar_protecoes(
    candidatos_base: List[int],
    historico: List[int],
    incluir_zero: bool = True,
    incluir_espelhos: bool = True,
    incluir_vizinhos: bool = True,
    max_protecoes: int = 6
) -> Dict[str, List[int]]:
    """
    Adiciona proteções aos candidatos base
    
    Args:
        candidatos_base: Lista de números principais
        historico: Histórico completo
        incluir_zero: Incluir o número 0
        incluir_espelhos: Incluir espelhos dos candidatos
        incluir_vizinhos: Incluir vizinhos dos candidatos
        max_protecoes: Máximo de proteções adicionais
    
    Returns:
        Dict com candidatos e proteções separados
    """
    protecoes = set()
    
    # 1. ZERO (sempre importante)
    if incluir_zero and 0 not in candidatos_base:
        protecoes.add(0)
    
    # 2. ESPELHOS dos candidatos
    if incluir_espelhos:
        for num in candidatos_base:
            if num in ESPELHOS:
                espelho = ESPELHOS[num]
                if espelho not in candidatos_base:
                    protecoes.add(espelho)
    
    # 3. VIZINHOS (1 de cada lado na roda)
    if incluir_vizinhos:
        for num in candidatos_base:
            vizinhos = get_vizinhos(num, distancia=1)
            for viz in vizinhos[:2]:  # Só os 2 mais próximos
                if viz not in candidatos_base and viz not in protecoes:
                    protecoes.add(viz)
    
    # 4. COMPLETAR RUAS (se 2 de 3 presentes)
    ruas = [
        [1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12],
        [13, 14, 15], [16, 17, 18], [19, 20, 21], [22, 23, 24],
        [25, 26, 27], [28, 29, 30], [31, 32, 33], [34, 35, 36]
    ]
    
    for rua in ruas:
        presentes = [n for n in rua if n in candidatos_base]
        if len(presentes) == 2:
            # 2 de 3 presentes, adiciona o faltante
            faltante = [n for n in rua if n not in candidatos_base][0]
            if faltante not in protecoes:
                protecoes.add(faltante)
    
    # 5. FAMÍLIA DE DEZENAS (se relevante)
    # Ex: se tem 2, 12, 22 → adiciona 32
    for terminal in range(10):
        familia = [n for n in [terminal, 10+terminal, 20+terminal, 30+terminal] 
                   if 0 <= n <= 36]
        presentes = [n for n in familia if n in candidatos_base]
        
        if len(presentes) >= 2:
            for num in familia:
                if num not in candidatos_base and num not in protecoes:
                    protecoes.add(num)
                    break  # Só adiciona 1 da família
    
    # Limita proteções ao máximo
    protecoes_lista = sorted(list(protecoes))[:max_protecoes]
    
    return {
        'candidatos': candidatos_base,
        'protecoes': protecoes_lista,
        'total_protegido': len(candidatos_base) + len(protecoes_lista)
    }


def identificar_faltantes(candidatos: List[int], historico: List[int], window: int = 30) -> List[int]:
    """
    Identifica faltantes (não apareceram recentemente)
    
    Args:
        candidatos: Lista de candidatos
        historico: Histórico completo
        window: Janela de análise
    
    Returns:
        Lista de números faltantes
    """
    recent_set = set(historico[:window])
    return [num for num in candidatos if num not in recent_set]


def calcular_consenso(
    candidatos: List[int],
    resultado_master,
    resultado_estelar,
    resultado_chain,
    resultado_temporal  # NOVO: 5º padrão
) -> Dict:
    """
    Calcula consenso entre os 5 padrões
    
    Returns:
        Dict com análise de consenso
    """
    set_candidatos = set(candidatos)
    set_master = set(resultado_master.scores.keys())
    set_estelar = set(resultado_estelar.scores.keys())
    set_chain = set(resultado_chain.scores.keys())
    
    # TEMPORAL retorna (candidates, metadata) - extrair set
    temporal_candidates = resultado_temporal[0] if isinstance(resultado_temporal, tuple) else {}
    set_temporal = set(temporal_candidates.keys())
    
    # Consenso total (5/5) - todos os padrões concordam
    consenso_total = set_candidatos & set_master & set_estelar & set_chain & set_temporal
    
    # Consenso quádruplo (4/5) - 4 padrões concordam
    mect = set_candidatos & set_master & set_estelar & set_chain & set_temporal - consenso_total
    mept = set_candidatos & set_master & set_estelar  & set_temporal - consenso_total
    mcpt = set_candidatos & set_master & set_chain  & set_temporal - consenso_total
    ecpt = set_candidatos & set_estelar & set_chain  & set_temporal - consenso_total
    mecp = set_candidatos & set_master & set_estelar & set_chain  - consenso_total
    
    # Consenso triplo (3/5) - 3 padrões concordam
    met = set_candidatos & set_master & set_estelar & set_temporal - consenso_total - mect - mept
    mct = set_candidatos & set_master & set_chain & set_temporal - consenso_total - mect - mcpt
    mpt = set_candidatos & set_master & set_temporal - consenso_total - mept - mcpt
    ect = set_candidatos & set_estelar & set_chain & set_temporal - consenso_total - mect - ecpt
    ept = set_candidatos & set_estelar & set_temporal - consenso_total - mept - ecpt
    cpt = set_candidatos & set_chain & set_temporal - consenso_total - mcpt - ecpt
    mec = set_candidatos & set_master & set_estelar & set_chain - consenso_total - mect - mecp
    mep = set_candidatos & set_master & set_estelar - consenso_total - mept - mecp
    mcp = set_candidatos & set_master & set_chain - consenso_total - mcpt - mecp
    ecp = set_candidatos & set_estelar & set_chain - consenso_total - ecpt - mecp
    
    # Consenso duplo (2/5)
    me = set_candidatos & set_master & set_estelar - (consenso_total | mect | mept | mecp | met | mec | mep)
    mc = set_candidatos & set_master & set_chain - (consenso_total | mect | mcpt | mecp | mct | mec | mcp)
    mp = set_candidatos & set_master  - (consenso_total | mept | mcpt | mecp | mpt | mep | mcp)
    mt = set_candidatos & set_master & set_temporal - (consenso_total | mect | mept | mcpt | met | mct | mpt)
    ec = set_candidatos & set_estelar & set_chain - (consenso_total | mect | ecpt | mecp | ect | mec | ecp)
    ep = set_candidatos & set_estelar  - (consenso_total | mept | ecpt | mecp | ept | mep | ecp)
    et = set_candidatos & set_estelar & set_temporal - (consenso_total | mect | mept | ecpt | met | ect | ept)
    cp = set_candidatos & set_chain  - (consenso_total | mcpt | ecpt | mecp | cpt | mcp | ecp)
    ct = set_candidatos & set_chain & set_temporal - (consenso_total | mect | mcpt | ecpt | mct | ect | cpt)
    pt = set_candidatos  & set_temporal - (consenso_total | mept | mcpt | ecpt | mpt | ept | cpt)
    
    # Únicos (apenas 1 padrão)
    so_master = set_candidatos & set_master - set_estelar - set_chain  - set_temporal
    so_estelar = set_candidatos & set_estelar - set_master - set_chain  - set_temporal
    so_chain = set_candidatos & set_chain - set_master - set_estelar  - set_temporal
    so_puxadas = set_candidatos  - set_master - set_estelar - set_chain - set_temporal
    so_temporal = set_candidatos & set_temporal - set_master - set_estelar - set_chain 
    
    return {
        'consenso_total': sorted(list(consenso_total)),
        'consenso_quadruplo': {
            'master_estelar_chain_temporal': sorted(list(mect)),
            'master_estelar_puxadas_temporal': sorted(list(mept)),
            'master_chain_puxadas_temporal': sorted(list(mcpt)),
            'estelar_chain_puxadas_temporal': sorted(list(ecpt)),
            'master_estelar_chain_puxadas': sorted(list(mecp))
        },
        'consenso_triplo': {
            'master_estelar_temporal': sorted(list(met)),
            'master_chain_temporal': sorted(list(mct)),
            'master_puxadas_temporal': sorted(list(mpt)),
            'estelar_chain_temporal': sorted(list(ect)),
            'estelar_puxadas_temporal': sorted(list(ept)),
            'chain_puxadas_temporal': sorted(list(cpt)),
            'master_estelar_chain': sorted(list(mec)),
            'master_estelar_puxadas': sorted(list(mep)),
            'master_chain_puxadas': sorted(list(mcp)),
            'estelar_chain_puxadas': sorted(list(ecp))
        },
        'consenso_duplo': {
            'master_estelar': sorted(list(me)),
            'master_chain': sorted(list(mc)),
            'master_puxadas': sorted(list(mp)),
            'master_temporal': sorted(list(mt)),
            'estelar_chain': sorted(list(ec)),
            'estelar_puxadas': sorted(list(ep)),
            'estelar_temporal': sorted(list(et)),
            'chain_puxadas': sorted(list(cp)),
            'chain_temporal': sorted(list(ct)),
            'puxadas_temporal': sorted(list(pt))
        },
        'unicos': {
            'master': sorted(list(so_master)),
            'estelar': sorted(list(so_estelar)),
            'chain': sorted(list(so_chain)),
            'puxadas': sorted(list(so_puxadas)),
            'temporal': sorted(list(so_temporal))
        }
    }


@router.get("/{roulette_id}", response_class=HTMLResponse)
async def sugestao_ensemble(
    request: Request,
    roulette_id: str,
    quantidade: int = Query(default=18, ge=1, le=28, description="Quantidade de sugestões principais"),
    incluir_protecoes: bool = Query(default=True, description="Incluir proteções (espelhos, vizinhos)"),
    max_protecoes: int = Query(default=6, ge=0, le=10, description="Máximo de proteções adicionais"),
    w_master: float = Query(default=0.20, ge=0, le=1, description="Peso do MASTER"),
    w_estelar: float = Query(default=0.20, ge=0, le=1, description="Peso do ESTELAR"),
    w_chain: float = Query(default=0.20, ge=0, le=1, description="Peso do CHAIN"),
    w_puxadas: float = Query(default=0.20, ge=0, le=1, description="Peso do PUXADAS"),
    w_temporal: float = Query(default=0.20, ge=0, le=1, description="Peso do TEMPORAL"),  # NOVO
    incluir_zero: bool = Query(default=True, description="Sempre incluir zero nas proteções"),
    limite_historico: int = Query(default=2000, ge=100, le=5000, description="Quantidade de histórico"),
    # Parâmetros do TEMPORAL (NOVOS)
    target_time: str = Query(default=None, description="Horário para análise temporal (HH:MM). Se None, usa horário atual"),
    interval_minutes: int = Query(default=3, ge=1, le=30, description="Intervalo em minutos para análise temporal"),
    days_back: int = Query(default=30, ge=7, le=90, description="Quantos dias analisar no padrão temporal")
):
    """
    Sugestão completa com Ensemble MASTER + ESTELAR + CHAIN + PUXADAS + TEMPORAL
    
    ## Parâmetros:
    
    - **quantidade**: Número de sugestões principais (1-12)
    - **incluir_protecoes**: Adicionar proteções automáticas
    - **max_protecoes**: Máximo de números de proteção (0-10)
    - **w_master**: Peso do MASTER no ensemble (0-1)
    - **w_estelar**: Peso do ESTELAR no ensemble (0-1)
    - **w_chain**: Peso do CHAIN no ensemble (0-1)
    - **w_puxadas**: Peso do PUXADAS no ensemble (0-1)
    - **w_temporal**: Peso do TEMPORAL no ensemble (0-1)
    - **incluir_zero**: Incluir zero automaticamente
    - **limite_historico**: Quantidade de histórico a analisar
    - **target_time**: Horário específico para análise temporal (HH:MM)
    - **interval_minutes**: Intervalo de tempo para análise temporal (1-30 min)
    - **days_back**: Período de histórico para análise temporal (7-90 dias)
    
    ## Retorna:
    
    - Lista de sugestões principais
    - Proteções (se habilitado)
    - Análise de consenso
    - Faltantes identificados
    - Metadados dos 3 padrões
    """
    try:
        db = request.app.state.db
        
        # Busca histórico
        logger.info(f"Buscando histórico para {roulette_id} (limite: {limite_historico})")
        numeros = await _get_historico_interno(request, roulette_id)
        
        if not numeros or len(numeros) < 50:
            raise HTTPException(
                status_code=404,
                detail=f"Histórico insuficiente para {roulette_id} (mínimo: 50 números)"
            )
        
        logger.info(f"Histórico obtido: {len(numeros)} números")
        
        # Configurações dos padrões
        config_master = {
            'enable_combined': True,     # Habilita D1Par, D2Ímpar, etc
            'enable_blocks': True,       # Habilita bloqueios (ciclo exausto)
            'cycle_detection': True,     # Detecta ciclos completos
            'verbose': False             # Modo silencioso
        }
        
        
        config_chain = {
            "min_chain_support": 2,
            "chain_decay": 0.95,
            "recent_window_miss": 30,
            "max_chain_length": 4
        }



        config = {
        'max_gap_between_elements': 2,
        'memory_short': 10,
        'memory_long': 200,
        'enable_inversions': True,
        'enable_compensation': True,
        'verbose': False,
        'equivalence_weights': {
            'EXACT': 1.0,
            'NEIGHBOR': 0.8,
            'TERMINAL': 0.6,
            'MIRROR': 0.5,
            'PROPERTY': 0.4,
            'BEHAVIORAL': 0.3
        }
        }
        
        # Cria instância

        

        
        # Executa análises
        logger.info("Executando MASTER...")
        master = PatternMaster(config=config_master)
        resultado_master = master.analyze(numeros)
        

        logger.info("Executando ESTELAR...")
        estelar = PatternEstelar(config)
        resultado_estelar = estelar.analyze(numeros)
        
        
        logger.info("Executando CHAIN...")
        chain = ChainAnalyzer(config=config_chain)
        resultado_chain = chain.analyze(numeros)


        logger.info("Executando TEMPORAL...")
        TEMPORAL_CONFIG = {
            "interval_minutes": 2,
            "days_back": days_back,
            "min_occurrences": 1,
            "roulette_id": roulette_id,
        }
        
        temporal_pattern = TemporalPattern(**TEMPORAL_CONFIG)


        resultado_temporal = await temporal_pattern.analyze(
            numeros,
            target_time=target_time,
            roulette_id=roulette_id,
            interval_minutes=interval_minutes,
            days_back=days_back
        )
        
        logger.info(f"TEMPORAL: {resultado_temporal[1].get('candidates_found', 0)} candidatos encontrados")

        
        # Calcula ensemble 
        logger.info("Calculando ensemble...")
        scores_ensemble_rank = calcular_ensemble_rank(
            resultado_master,
            resultado_estelar,
            resultado_chain,
            resultado_temporal,  # NOVO
            w_master=w_master,
            w_estelar=w_estelar,
            w_chain=w_chain,
            w_temporal=w_temporal  # NOVO
        )

        scores_ensemble = calcular_ensemble(
            resultado_master,
            resultado_estelar,
            resultado_chain,
            resultado_temporal,  # NOVO
            w_master=w_master,
            w_estelar=w_estelar,
            w_chain=w_chain,
            w_temporal=w_temporal  # NOVO
        )
        
        
        # Ordena candidatos
        candidatos_ordenados = sorted(
            scores_ensemble.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Pega top N
        candidatos_top = [num for num, _ in candidatos_ordenados[:quantidade]]
        
        # Identifica faltantes
        faltantes = identificar_faltantes(candidatos_top, numeros, window=30)
        
        # Calcula consenso 
        consenso = calcular_consenso(
            candidatos_top,
            resultado_master,
            resultado_estelar,
            resultado_chain,
            resultado_temporal  # NOVO
        )
        
        # Aplica proteções
        if incluir_protecoes:
            protecoes_result = aplicar_protecoes(
                candidatos_top,
                numeros,
                incluir_zero=incluir_zero,
                incluir_espelhos=True,
                incluir_vizinhos=True,
                max_protecoes=max_protecoes
            )
        else:
            protecoes_result = {
                'candidatos': candidatos_top,
                'protecoes': [],
                'total_protegido': len(candidatos_top)
            }
        
        # Constrói resposta
        resposta = {
            "roulette_id": roulette_id,
            "timestamp": numeros[0] if numeros else None,
            "sugestoes": {
                "principais": [
                    {
                        "numero": num,
                        "score": round(scores_ensemble[num], 6),
                        "ranking": i + 1,
                        "faltante": num in faltantes,
                        "consenso": _get_consenso_nivel(num, consenso)
                    }
                    for i, num in enumerate(candidatos_top)
                ],
                "protecoes": [
                    {
                        "numero": num,
                        "tipo": _get_tipo_protecao(num, candidatos_top, numeros)
                    }
                    for num in protecoes_result['protecoes']
                ],
                "total_numeros": protecoes_result['total_protegido']
            },
            "analise": {
                "consenso": consenso,
                "faltantes": faltantes,
                "ultimo_numero": numeros[0],
                "ultimos_10": numeros[:10]
            },
            "padroes": {
                "master": {
                    "padroes_encontrados": resultado_master.metadata.get('padroes_encontrados', 0),
                    "modo": resultado_master.metadata.get('modo', 'normal'),
                    "top_3": [num for num, _ in resultado_master.get_top_n(5)]
                },
                "estelar": {
                    "padroes_equivalentes": resultado_estelar.metadata.get('padroes_equivalentes', 0),
                    "tipos": resultado_estelar.metadata.get('tipos_equivalencia', {}),
                    "top_3": [num for num, _ in resultado_estelar.get_top_n(18)]
                },
                "chain": {
                    "cadeias_aprendidas": resultado_chain.metadata.get('total_cadeias_aprendidas', 0),
                    "inversoes": resultado_chain.metadata.get('inversoes_detectadas', 0),
                    "compensacoes": resultado_chain.metadata.get('compensacoes_detectadas', 0),
                    "top_pares": resultado_chain.metadata.get('top_pares', [])[:5],
                    "top_3": [num for num, _ in resultado_chain.get_top_n(5)]
                },
                
                "temporal": {
                    "time_analyzed": resultado_temporal[1].get('time_analyzed', ''),
                    "interval_minutes": resultado_temporal[1].get('interval_minutes', 0),
                    "interval_end": resultado_temporal[1].get('interval_end', ''),
                    "days_analyzed": resultado_temporal[1].get('days_analyzed', 0),
                    "total_occurrences": resultado_temporal[1].get('total_occurrences', 0),
                    "days_with_data": resultado_temporal[1].get('days_with_data', 0),
                    "candidates_found": resultado_temporal[1].get('candidates_found', 0),
                    "top_5_historical": resultado_temporal[1].get('top_5_historical', [])[:18],
                    "roulette_id": resultado_temporal[1].get('roulette_id', roulette_id)
                }
            },
            "configuracao": {
                "pesos": {
                    "master": w_master,
                    "estelar": w_estelar,
                    "chain": w_chain,
                    "puxadas": w_puxadas,
                    "temporal": w_temporal
                },
                "temporal_config": {
                    "target_time": target_time,
                    "interval_minutes": interval_minutes,
                    "days_back": days_back
                },
                "quantidade_solicitada": quantidade,
                "protecoes_habilitadas": incluir_protecoes,
                "historico_analisado": len(numeros)
            }
        }
        
        logger.info(
            f"Sugestão gerada: {len(candidatos_top)} principais + "
            f"{len(protecoes_result['protecoes'])} proteções"
        )
        

        # Decide o tipo de resposta com base no header Accept
        accept = (request.headers.get("accept", "") or "").lower()

        # Se for chamada via fetch (Nova análise) pedindo JSON:
        if "application/json" in accept or "text/json" in accept:
            return JSONResponse(content=resposta)

        # Caso contrário, navegação normal do navegador → renderiza HTML
        return templates.TemplateResponse(
            "sugestao.html",
            {
                "request": request,
                "dados": resposta
            }
        )


        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar sugestão: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar sugestão: {str(e)}"
        )


def _get_consenso_nivel(numero: int, consenso: Dict) -> str:
    """Retorna nível de consenso de um número (5 padrões)"""
    if numero in consenso['consenso_total']:
        return "total_5/5"
    
    # Consenso quádruplo (4/5)
    for tipo, nums in consenso.get('consenso_quadruplo', {}).items():
        if numero in nums:
            return f"quadruplo_{tipo}"
    
    # Consenso triplo (3/5)
    for tipo, nums in consenso.get('consenso_triplo', {}).items():
        if numero in nums:
            return f"triplo_{tipo}"
    
    # Consenso duplo (2/5)
    for tipo, nums in consenso['consenso_duplo'].items():
        if numero in nums:
            return f"duplo_{tipo}"
    
    # Único (1/5)
    for tipo, nums in consenso['unicos'].items():
        if numero in nums:
            return f"unico_{tipo}"
    
    return "ensemble"


def _get_tipo_protecao(numero: int, candidatos: List[int], historico: List[int]) -> str:
    """Identifica tipo de proteção"""
    tipos = []
    
    if numero == 0:
        tipos.append("zero")
    
    # Verifica se é espelho
    for cand in candidatos:
        if cand in ESPELHOS and ESPELHOS[cand] == numero:
            tipos.append(f"espelho_de_{cand}")
            break
    
    # Verifica se é vizinho
    for cand in candidatos:
        vizinhos = get_vizinhos(cand, distancia=1)
        if numero in vizinhos:
            tipos.append(f"vizinho_de_{cand}")
            break
    
    # Verifica se completa rua
    ruas = [
        [1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12],
        [13, 14, 15], [16, 17, 18], [19, 20, 21], [22, 23, 24],
        [25, 26, 27], [28, 29, 30], [31, 32, 33], [34, 35, 36]
    ]
    
    for rua in ruas:
        if numero in rua:
            presentes = [n for n in rua if n in candidatos]
            if len(presentes) == 2:
                tipos.append(f"completa_rua_{rua}")
                break
    
    return ", ".join(tipos) if tipos else "protecao_geral"