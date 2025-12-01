"""
routes/sugestao.py

Rota para sugestões com Ensemble MASTER + ESTELAR + CHAIN
Inclui proteções dinâmicas (espelhos, vizinhos, zero)
"""

from fastapi import APIRouter, HTTPException, Query, Request
from typing import List, Dict, Set, Any
from collections import defaultdict
import logging

from patterns.puxadas import PuxadasPattern 
from patterns.master import PatternMaster
from patterns.estelar import PatternEstelar
from patterns.chain import ChainPattern
from patterns.temporal import TemporalPattern
from patterns.comportamental import create_comportamental_pattern


from patterns.numero_quente import HotNumbersPattern

from collections import defaultdict
from typing import Dict, List, Iterable, Optional

from utils.constants import ESPELHOS
from utils.helpers import get_vizinhos, get_espelho
from fastapi.responses import  JSONResponse, HTMLResponse

from fastapi.templating import Jinja2Templates


templates = Jinja2Templates(directory="templates")

from typing import Dict, List
from patterns.base import PatternResult

router = APIRouter()
logger = logging.getLogger(__name__)


# Ordem física da roleta europeia para detecção de buracos e isolados
WHEEL_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34,
    6, 27, 13, 36, 11, 30, 8, 23, 10, 5,
    24, 16, 33, 1, 20, 14, 31, 9, 22, 18,
    29, 7, 28, 12, 35, 3, 26
]
WHEEL_INDEX = {n: i for i, n in enumerate(WHEEL_ORDER)}


def calcular_indice_confianca_global(
    candidatos_top: List[int],
    scores_ensemble: Dict[int, float],
    resultado_estelar: PatternResult,
    resultado_chain: PatternResult,
    resultado_temporal: PatternResult,
    resultado_quente: PatternResult,
    resultado_comport: PatternResult,
) -> Dict:
    """
    Calcula índice de confiança global e por número, considerando
    quantos padrões (Estelar, Chain, Temporal, Quente) suportam
    cada número e ponderando pelos scores do ensemble.
    """

    if not candidatos_top:
        return {
            "valor": 0.0,
            "nivel": "baixo",
            "detalhes": {
                "media_padroes_por_numero": 0.0,
                "max_padroes_numero": 0,
            },
            "por_numero": {},
        }

    # Mapas de presença por padrão
    estelar_scores = resultado_estelar.scores or {}
    chain_scores = resultado_chain.scores or {}
    temporal_scores = resultado_temporal.scores or {}
    quente_scores = resultado_quente.scores or {}
    comport_scores = resultado_comport.scores or {}

    padroes_total = 5.0  # estelar, chain, temporal, quente

    # Normalizar pesos do ensemble só nos candidatos_top
    raw_scores = [scores_ensemble.get(n, 0.0) for n in candidatos_top]
    soma_scores = sum(raw_scores)
    if soma_scores <= 0:
        # fallback: peso uniforme
        pesos = {n: 1.0 / len(candidatos_top) for n in candidatos_top}
    else:
        pesos = {
            n: (scores_ensemble.get(n, 0.0) / soma_scores)
            for n in candidatos_top
        }

    por_numero: Dict[int, float] = {}
    total_padroes = 0
    max_padroes = 0
    cobertura_ponderada = 0.0

    for n in candidatos_top:
        cnt = 0
        if n in estelar_scores:
            cnt += 1
        if n in chain_scores:
            cnt += 1
        if n in temporal_scores:
            cnt += 1
        if n in quente_scores:
            cnt += 1
        if n in comport_scores:
            cnt += 1

        max_padroes = max(max_padroes, cnt)
        total_padroes += cnt

        # confiança daquele número = proporção de padrões que o apoiam
        conf_n = cnt / padroes_total
        por_numero[n] = conf_n

        cobertura_ponderada += conf_n * pesos.get(n, 0.0)

    media_padroes_por_numero = (
        total_padroes / (len(candidatos_top) * padroes_total)
        if candidatos_top else 0.0
    )
    max_padroes_norm = max_padroes / padroes_total

    # índice global: mistura de média ponderada + melhor caso
    indice = 0.7 * cobertura_ponderada + 0.5 * max_padroes_norm

    # nível qualitativo
    if indice >= 0.7:
        nivel = "alto"
    elif indice >= 0.4:
        nivel = "medio"
    else:
        nivel = "baixo"

    return {
        "valor": round(indice, 4),
        "nivel": nivel,
        "detalhes": {
            "media_padroes_por_numero": round(media_padroes_por_numero, 4),
            "max_padroes_numero": max_padroes,
        },
        "por_numero": por_numero,
    }

def aplicar_regra_fixos_ensemble(
    bet_numbers: list[int],
    history: list[int],
) -> list[int]:
    """
    Ajusta a lista de aposta quando há mais de 25 fichas,
    garantindo que alguns números fixos SEMPRE estejam na aposta:

    - último número sorteado
    - penúltimo número
    - espelho(s) do último
    - vizinhos dos espelhos do último
    - (last-1) e (last+1), se entre 0 e 36
    - vizinhos do último número

    Mantém o mesmo tamanho da lista, apenas trocando números do final.
    """

    # Só aplicamos se tiver histórico suficiente e muitas fichas
    if len(bet_numbers) <= 20 or len(history) < 2:
        return bet_numbers

    # history deve estar com MAIS RECENTE no índice 0 (como no resto da API)
    ultimo = history[0]
    penultimo = history[1]

    fixos_ordenados: list[int] = []

    # 1) último e penúltimo
    fixos_ordenados.append(ultimo)
    fixos_ordenados.append(penultimo)
  
    # 2) espelho(s) do último
    mirrors = get_espelho(ultimo)
    if isinstance(mirrors, int):
        mirrors = [mirrors]
    for m in mirrors:
        if 0 <= m <= 36:
            fixos_ordenados.append(m)

    # 3) vizinhos dos espelhos
    for m in mirrors:
        if not (0 <= m <= 36):
            continue
        try:
            vizinhos_m = get_vizinhos(m)
        except Exception:
            vizinhos_m = []
        for v in vizinhos_m:
            if 0 <= v <= 36:
                fixos_ordenados.append(v)


    # 4) número acima e abaixo do último (ex.: 13 e 15 se veio 14)
    if 0 <= ultimo - 1 <= 36:
        fixos_ordenados.append(ultimo - 1)
    if 0 <= ultimo + 1 <= 36:
        fixos_ordenados.append(ultimo + 1)

    # 4) número acima e abaixo do último (ex.: 13 e 15 se veio 14)
    if 0 <= penultimo - 1 <= 36:
        fixos_ordenados.append(penultimo - 1)
    if 0 <= penultimo + 1 <= 36:
        fixos_ordenados.append(penultimo + 1)

    # 5) vizinhos do último número
    try:
        vizinhos_ultimo = get_vizinhos(ultimo)
    except Exception:
        vizinhos_ultimo = []
    for v in vizinhos_ultimo:
        if 0 <= v <= 36:
            fixos_ordenados.append(v)

    # Normalizar: tirar duplicados mantendo ordem
    vistos = set()
    fixos_ordenados_unicos: list[int] = []
    for n in fixos_ordenados:
        if n not in vistos and 0 <= n <= 36:
            vistos.add(n)
            fixos_ordenados_unicos.append(n)

    # Conjunto para checagens rápidas
    fixos_set = set(fixos_ordenados_unicos)

    # Trabalhar em cópia da lista de aposta
    aposta = list(bet_numbers)

    # Para cada número fixo, garantir que ele esteja na aposta
    for num_fixo in fixos_ordenados_unicos:
        # Se já está, não faz nada
        if num_fixo in aposta:
            continue

        # Se não está, precisamos remover alguém do FINAL que não é "fixo"
        # e colocar esse número no lugar
        idx = len(aposta) - 1
        while idx >= 0:
            candidato_remocao = aposta[idx]

            # Não removemos nenhum número que também esteja no conjunto de fixos
            if candidato_remocao in fixos_set:
                idx -= 1
                continue

            # Remover esse número e inserir o fixo
            aposta.pop(idx)
            aposta.append(num_fixo)
            break  # segue para o próximo número fixo

        # Se não encontrou ninguém para remover, apenas segue
        # (isso significa que praticamente todos já são "fixos")

    return aposta


def _wheel_distance(a: int, b: int) -> int:
    """Distância circular na roda física entre dois números."""
    if a not in WHEEL_INDEX or b not in WHEEL_INDEX:
        return 999
    n = len(WHEEL_ORDER)
    ia = WHEEL_INDEX[a]
    ib = WHEEL_INDEX[b]
    diff = abs(ia - ib)
    return min(diff, n - diff)


def _clusterizar_por_roda(
    scores_ensemble: Dict[int, float],
    dist_cluster: int = 1,
    min_score: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Cria clusters de números pela proximidade na roda,
    priorizando os números com maior score.

    Retorna lista de clusters:
    [
      {
        "nucleos": {13, 11}, 
        "espelhos": {31},
        "membros": {13, 36, 11, 31},
        "forca": 2.45,  # soma ponderada
        "scores": {numero: score}
      },
      ...
    ]
    """
    # filtra números válidos e ordena por score desc
    candidatos = [
        (n, sc)
        for n, sc in scores_ensemble.items()
        if 0 <= n <= 36 and sc >= min_score
    ]
    candidatos.sort(key=lambda x: x[1], reverse=True)

    clusters: List[Dict[str, Any]] = []

    for numero, sc in candidatos:
        if numero not in WHEEL_INDEX:
            continue

        melhor_cluster = None
        melhor_dist = 999

        for cl in clusters:
            # aproximação: mede distância até qualquer núcleo do cluster
            for nucleo in cl["nucleos"]:
                d = _wheel_distance(numero, nucleo)
                if d <= dist_cluster and d < melhor_dist:
                    melhor_dist = d
                    melhor_cluster = cl

        if melhor_cluster is None:
            # cria novo cluster com este número como núcleo
            clusters.append({
                "nucleos": {numero},
                "espelhos": set(),
                "membros": {numero},
                "forca": sc,
                "scores": {numero: sc},
            })
        else:
            melhor_cluster["membros"].add(numero)
            melhor_cluster["forca"] += sc
            melhor_cluster["scores"][numero] = sc
            # se ele for muito forte em relação ao cluster, vira núcleo também
            melhor_cluster["nucleos"].add(numero)

    # adiciona espelhos dentro dos clusters
    usados = set()
    for cl in clusters:
        usados.update(cl["membros"])

    for cl in clusters:
        for nucleo in list(cl["nucleos"]):
            esp = ESPELHOS.get(nucleo)
            if esp is None or not (0 <= esp <= 36):
                continue
            if esp in usados:
                # já está em algum cluster (pode ser no mesmo)
                if esp in cl["membros"]:
                    cl["espelhos"].add(esp)
                continue

            # adiciona espelho no mesmo cluster com peso levemente menor
            sc_nucleo = cl["scores"].get(nucleo, 0.0)
            sc_esp = sc_nucleo * 0.9
            cl["espelhos"].add(esp)
            cl["membros"].add(esp)
            cl["scores"][esp] = sc_esp
            cl["forca"] += sc_esp
            usados.add(esp)

    # ordena clusters por força decrescente
    clusters.sort(key=lambda c: c["forca"], reverse=True)
    return clusters


def gerar_numeros_agrupados_por_regiao(
    scores_ensemble: Dict[int, float],
    dist_cluster: int = 1,
    min_score: float = 0.0
) -> List[int]:
    """
    Gera lista de números já agrupados por região:

    - Prioriza clusters mais fortes (soma de scores).
    - Dentro de cada cluster:
        1) núcleos (ordenados por score)
        2) espelhos dos núcleos
        3) demais membros (buracos internos)

    Você decide depois quantos usar (12, 14, 16, 18...).
    """
    clusters = _clusterizar_por_roda(
        scores_ensemble=scores_ensemble,
        dist_cluster=dist_cluster,
        min_score=min_score,
    )

    resultado: List[int] = []
    usados: set[int] = set()

    for cl in clusters:
        scores = cl["scores"]

        # 1) núcleos ordenados por score
        nucleos_ordenados = sorted(
            list(cl["nucleos"]),
            key=lambda n: scores.get(n, 0.0),
            reverse=True,
        )

        # 2) espelhos dos núcleos (se existirem no cluster)
        espelhos_ordenados = sorted(
            list(cl["espelhos"]),
            key=lambda n: scores.get(n, 0.0),
            reverse=True,
        )

        # 3) demais membros (buracos internos / números da região)
        outros = [
            n for n in cl["membros"]
            if n not in cl["nucleos"] and n not in cl["espelhos"]
        ]
        outros_ordenados = sorted(
            outros,
            key=lambda n: scores.get(n, 0.0),
            reverse=True,
        )

        for n in nucleos_ordenados + espelhos_ordenados + outros_ordenados:
            if n not in usados:
                usados.add(n)
                resultado.append(n)

    return resultado



def _get_wheel_neighbors(numero: int, distancia: int = 1) -> List[int]:
    """
    Retorna vizinhos na roda física a uma determinada distância.
    """
    if numero not in WHEEL_INDEX:
        return []
    idx = WHEEL_INDEX[numero]
    n = len(WHEEL_ORDER)
    vizinhos = []
    for d in range(1, distancia + 1):
        vizinhos.append(WHEEL_ORDER[(idx - d) % n])
        vizinhos.append(WHEEL_ORDER[(idx + d) % n])
    return vizinhos

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
    resultado_estelar,
    resultado_chain,
    resultado_temporal, 
    resultado_quente, 
    resultado_comport,
    w_estelar: float = 0.10,
    w_chain: float = 0.5,
    w_temporal: float = 0.10,
    w_quente: float = 0.30,
    w_comport: float = 0.30,
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
    # Combina scores
    scores_combinados = defaultdict(float)
    
    
    # ESTELAR
    for num, score in resultado_estelar.scores.items():
        scores_combinados[num] += w_estelar * score
    
    # CHAIN
    for num, score in resultado_chain.scores.items():
        scores_combinados[num] += w_chain * score
    
    # TEMPORAL 
    for num, score in resultado_temporal.scores.items():
        scores_combinados[num] += w_temporal * score

    for num, score in resultado_quente.scores.items():
        scores_combinados[num] += w_quente * score

    for num, score in resultado_comport.scores.items():
        scores_combinados[num] += w_comport * score
    
    # Normaliza resultado final
    if scores_combinados:
        max_score = max(scores_combinados.values())
        if max_score > 0:
            scores_combinados = {
                num: score / max_score
                for num, score in scores_combinados.items()
            }
    
    return dict(scores_combinados)



def detectar_buracos_entre_candidatos(candidatos: List[int]) -> List[int]:
    """
    Detecta números que são 'buracos' entre dois vizinhos já sugeridos
    na roda física. Ex.: 35 e 28 sugeridos → 12 é buraco.
    """
    if not candidatos:
        return []
    candidatos_set = set(candidatos)
    buracos = set()

    for numero in WHEEL_ORDER:
        if numero in candidatos_set:
            continue
        # ignorar zero como buraco
        if numero == 0:
            continue
        vizinhos = _get_wheel_neighbors(numero, distancia=1)
        # se os dois vizinhos imediatos estão sugeridos, este número é buraco
        if len(vizinhos) >= 2 and all(v in candidatos_set for v in vizinhos[:2]):
            buracos.add(numero)

    return sorted(buracos)


def detectar_vizinhos_para_isolados(
    candidatos: List[int],
    scores: Dict[int, float],
    min_score: float = 0.6,
    depth: int = 1,
    max_extra_por_nucleo: int = 2,
) -> List[int]:
    """
    Para cada candidato 'isolado' (sem vizinhos sugeridos na roda),
    adiciona vizinhos como proteção, desde que o núcleo seja forte o suficiente.

    - min_score: score mínimo do núcleo para compensar a proteção
    - depth: quantas casas olhar (1 = vizinhos imediatos)
    - max_extra_por_nucleo: quantos vizinhos adicionar por núcleo
    """
    if not candidatos:
        return []

    candidatos_set = set(candidatos)
    extras = set()

    for numero in candidatos:
        core_score = scores.get(numero, 0.0)
        if core_score < min_score:
            continue

        if numero not in WHEEL_INDEX:
            continue

        idx = WHEEL_INDEX[numero]
        n = len(WHEEL_ORDER)

        vizinhos = []
        for d in range(1, depth + 1):
            vizinhos.append(WHEEL_ORDER[(idx - d) % n])
            vizinhos.append(WHEEL_ORDER[(idx + d) % n])

        # núcleo é isolado se nenhum vizinho está sugerido
        if any(v in candidatos_set for v in vizinhos):
            continue

        # adiciona vizinhos imediatos como proteção
        adicionados = 0
        for v in vizinhos:
            if adicionados >= max_extra_por_nucleo:
                break
            if v not in candidatos_set and v not in extras:
                extras.add(v)
                adicionados += 1

    return sorted(extras)





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
        for num in candidatos_base[:4]:
            if num in ESPELHOS:
                espelho = ESPELHOS[num]
                if espelho not in candidatos_base:
                    protecoes.add(espelho)
    
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


from typing import List, Dict, Set

def calcular_consenso(
    candidatos: List[int],
    resultado_estelar,
    resultado_chain,
    resultado_temporal,
    resultado_quente,
    resultado_comport
) -> Dict:
    """
    Calcula consenso entre Estelar, Chain, Temporal e Quente
    RESTRITO aos números que estão nos candidatos (ensemble final).

    Retorna:
        {
            'consenso_4': [...],
            'consenso_3': [...],
            'consenso_2': [...],
            'unicos': {
                'estelar': [...],
                'chain': [...],
                'temporal': [...],
                'quente': [...],
            }
        }
    """
    set_final = set(candidatos)

    sets_por_padrao: Dict[str, Set[int]] = {
        "estelar": set(resultado_estelar.scores.keys()) if resultado_estelar and resultado_estelar.scores else set(),
        "chain": set(resultado_chain.scores.keys()) if resultado_chain and resultado_chain.scores else set(),
        "temporal": set(resultado_temporal.scores.keys()) if resultado_temporal and resultado_temporal.scores else set(),
        "quente": set(resultado_quente.scores.keys()) if resultado_quente and resultado_quente.scores else set(),
        "comportamental": set(resultado_comport.scores.keys()) if resultado_comport and resultado_comport.scores else set(),
    }

    # Interessa só a interseção com o conjunto final
    sets_restritos = {
        nome: s & set_final
        for nome, s in sets_por_padrao.items()
    }

    # Mapa numero -> conj(de padrões onde ele aparece)
    presencas: Dict[int, Set[str]] = {}
    for nome, s in sets_restritos.items():
        for n in s:
            if n not in presencas:
                presencas[n] = set()
            presencas[n].add(nome)

    consenso_5 = []
    consenso_4 = []
    consenso_3 = []
    consenso_2 = []

    for n, pats in presencas.items():
        k = len(pats)
        if k == 5:
            consenso_5.append(n)
        if k == 4:
            consenso_4.append(n)
        elif k == 3:
            consenso_3.append(n)
        elif k == 2:
            consenso_2.append(n)

    # Unicos por padrão (apenas naquele padrão)
    unicos = {
        nome: sorted([
            n for n, pats in presencas.items()
            if pats == {nome}
        ])
        for nome in ["estelar", "chain", "temporal", "quente"]
    }

    return {
        "consenso_5": sorted(consenso_5),
        "consenso_4": sorted(consenso_4),
        "consenso_3": sorted(consenso_3),
        "consenso_2": sorted(consenso_2),
        "unicos": unicos,
    }


@router.get("/{roulette_id}", response_class=HTMLResponse)
async def sugestao_ensemble(
    request: Request,
    roulette_id: str,
    quantidade: int = Query(default=18, ge=1, le=35, description="Quantidade de sugestões principais"),
    incluir_protecoes: bool = Query(default=True, description="Incluir proteções (espelhos, vizinhos)"),
    max_protecoes: int = Query(default=6, ge=0, le=10, description="Máximo de proteções adicionais"),
    w_estelar: float = Query(default=0.20, ge=0, le=1, description="Peso do ESTELAR"),
    w_chain: float = Query(default=0.20, ge=0, le=1, description="Peso do CHAIN"),
    w_quente: float = Query(default=0.20, ge=0, le=1, description="Peso do PUXADAS"),
    w_comport: float = Query(default=0.20, ge=0, le=1, description="Peso do PUXADAS"),
    w_temporal: float = Query(default=0.20, ge=0, le=1, description="Peso do TEMPORAL"),  # NOVO
    incluir_zero: bool = Query(default=True, description="Sempre incluir zero nas proteções"),
    limite_historico: int = Query(default=200, ge=100, le=5000, description="Quantidade de histórico"),
    cover_holes=True,
    cover_isolated=True,
    isolated_min_core_score=0.6,
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
                
        # Busca histórico
        logger.info(f"Buscando histórico para {roulette_id} (limite: {limite_historico})")
        numeros = await _get_historico_interno(request, roulette_id, limite_historico)
        
        if not numeros or len(numeros) < 50:
            raise HTTPException(
                status_code=404,
                detail=f"Histórico insuficiente para {roulette_id} (mínimo: 50 números)"
            )
        
        logger.info(f"Histórico obtido: {len(numeros)} números")
        
        
        config = {
        'max_gap_between_elements': 2,
        'memory_short': 10,
        'memory_long': limite_historico,
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
        

        logger.info("Executando ESTELAR...")
        estelar = PatternEstelar(config)
        resultado_estelar = estelar.analyze(numeros)
        
        
        logger.info("Executando CHAIN...")
        chain = ChainPattern()
        resultado_chain = chain.analyze(numeros)


        logger.info("Executando TEMPORAL...")
        TEMPORAL_CONFIG = {
            "interval_minutes": 2,
            "days_back": days_back,
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

        logger.info("Executando Numeros quentes...")
        hot_pattern = HotNumbersPattern()
        resultado_quente = hot_pattern.analyze(numeros)  # mesma history que você já usa
        

        pattern_comport = create_comportamental_pattern()
        resultado_comport = pattern_comport.analyze(numeros)

        # 4. Calcular ensemble de scores (SINAL BRUTO)
        scores_ensemble = calcular_ensemble(
            resultado_estelar,
            resultado_chain,
            resultado_temporal,
            resultado_quente,
            resultado_comport,
            w_estelar=w_estelar,
            w_chain=w_chain,
            w_temporal=w_temporal,
            w_quente=w_quente,
            w_comport=w_comport   
        )

        # -----------------------------
        # A) TOP BRUTO (sem compactar)
        # -----------------------------
        # ordena pelo score bruto do ensemble
        ordenados_bruto = sorted(
            scores_ensemble.items(),
            key=lambda x: x[1],
            reverse=True
        )

        candidatos_top_bruto = [n for n, _ in ordenados_bruto[:quantidade]]

        # Consenso calculado no BRUTO
        consenso_bruto = calcular_consenso(
            candidatos_top_bruto,
            resultado_estelar,
            resultado_chain,
            resultado_temporal,
            resultado_quente,
            resultado_comport
        )

        # -----------------------------
        # B) COMPACTAÇÃO (APOSTA FINAL)
        # -----------------------------
        numeros_agrupados = gerar_numeros_agrupados_por_regiao(
            scores_ensemble=scores_ensemble,
            dist_cluster=2,
            min_score=0.0
        )

        candidatos_top = numeros_agrupados[:quantidade]

        # aplica regra fixos na APOSTA FINAL
        candidatos_top = aplicar_regra_fixos_ensemble(
            bet_numbers=candidatos_top,
            history=numeros,
        )

        

        # Índice de confiança calculado no BRUTO
        indice_confianca = calcular_indice_confianca_global(
            candidatos_top=candidatos_top_bruto,
            scores_ensemble=scores_ensemble,
            resultado_estelar=resultado_estelar,
            resultado_chain=resultado_chain,
            resultado_temporal=resultado_temporal,
            resultado_quente=resultado_quente,
            resultado_comport=resultado_comport,
        )


        # Identifica faltantes na APOSTA FINAL (porque faltante é sobre o que você vai jogar)
        faltantes = identificar_faltantes(candidatos_top, numeros, window=30)

        # Se quiser manter no payload:
        consenso = consenso_bruto
        
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


        # Proteções adicionais: buracos e números isolados
        protecoes_buracos: List[int] = []
        protecoes_isolados: List[int] = []

        if incluir_protecoes and max_protecoes > 0:
            protecoes_set = set(protecoes_result.get('protecoes', []))
             # 1) Cobrir buracos entre vizinhos na roda
            if cover_holes:
                buracos = detectar_buracos_entre_candidatos(candidatos_top)
                for n in buracos:
                    if len(protecoes_set) >= max_protecoes:
                        break
                    if n not in candidatos_top and n not in protecoes_set:
                        protecoes_set.add(n)
                        protecoes_buracos.append(n)

            # 2) Cobrir números isolados fortes
            if cover_isolated:
                extras_isolados = detectar_vizinhos_para_isolados(
                    candidatos_top,
                    scores_ensemble,
                    min_score=isolated_min_core_score,
                    depth=1,
                    max_extra_por_nucleo=2,
                )
                for n in extras_isolados:
                    if len(protecoes_set) >= max_protecoes:
                        break
                    if n not in candidatos_top and n not in protecoes_set:
                        protecoes_set.add(n)
                        protecoes_isolados.append(n)

            protecoes_result['protecoes'] = sorted(protecoes_set)
            protecoes_result['total_protegido'] = len(candidatos_top) + len(protecoes_result['protecoes'])
        else:
            protecoes_buracos = []
            protecoes_isolados = []
        
        # Constrói resposta
        resposta = {
            "roulette_id": roulette_id,
            "timestamp": numeros[0] if numeros else None,
            "historico" : numeros[:50],
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
                "ultimos_10": numeros[:10],
                "confianca": indice_confianca,
            },
            "padroes": {
                "estelar": {
                    "padroes_equivalentes": resultado_estelar.metadata.get('padroes_equivalentes', 0),
                    "tipos": resultado_estelar.metadata.get('tipos_equivalencia', {}),
                    "top_18": [num for num, _ in resultado_estelar.get_top_n(12)],
                },
                "chain": {
                    "cadeias_aprendidas": resultado_chain.metadata.get('total_cadeias_aprendidas', 0),
                    "inversoes": resultado_chain.metadata.get('inversoes_detectadas', 0),
                    "compensacoes": resultado_chain.metadata.get('compensacoes_detectadas', 0),
                    "top_18": [num for num, _ in resultado_chain.get_top_n(12)]
                },
                "temporal": {
                    "time_analyzed": resultado_temporal.metadata.get('time_analyzed', ''),
                    "interval_minutes": resultado_temporal.metadata.get('interval_minutes', 0),
                    "interval_end": resultado_temporal.metadata.get('interval_end', ''),
                    "days_analyzed": resultado_temporal.metadata.get('days_analyzed', 0),
                    "total_occurrences": resultado_temporal.metadata.get('total_occurrences', 0),
                    "days_with_data": resultado_temporal.metadata.get('days_with_data', 0),
                    "candidates_found": resultado_temporal.metadata.get('candidates_found', 0),
                    "top_18": [num for num, _ in resultado_temporal.get_top_n(12)],
                    "roulette_id": resultado_temporal.metadata.get('roulette_id', roulette_id)
                },
                "quente": {
                    "window_size": resultado_quente.metadata.get('window_size', 0),
                    "window_size_real": resultado_quente.metadata.get('window_size_real', 0),
                    "short_window": resultado_quente.metadata.get('short_window', 0),
                    "expected_per_number": resultado_quente.metadata.get('expected_per_number', 0.0),
                    "top_18": [num for num, _ in resultado_quente.get_top_n(12)],
                    "top_hot_debug": resultado_quente.metadata.get('top_hot', [])
                },

                "comportamental": {
                    "top_18": [num for num, _ in resultado_comport.get_top_n(12)],
                }
            },
            "configuracao": {
                "pesos": {
                    "estelar": w_estelar,
                    "chain": w_chain,
                    "temporal": w_temporal,
                    "quente": w_quente,
                    "comportamental" : 2.0
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
    """
    Retorna nível de consenso de um número considerando 4 padrões:
    - estelar
    - chain
    - temporal
    - quente
    """
    # 4/4 padrões
    if numero in consenso.get("consenso_4", []):
        return "total_4/4"
    
    # 3/4 padrões
    if numero in consenso.get("consenso_3", []):
        return "triplo_3/4"
    
    # 2/4 padrões
    if numero in consenso.get("consenso_2", []):
        return "duplo_2/4"
    
    # Único em um padrão específico
    for padrao, nums in consenso.get("unicos", {}).items():
        if numero in nums:
            return f"unico_{padrao}"
    
    # Está só no ensemble final, mas não entra em nenhum grupo acima
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