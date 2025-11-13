"""
utils/constants.py

Constantes utilizadas em toda a aplicação
Baseado nos padrões Master + Estelar + Chain
"""

from typing import Dict, List

# ========== RODA EUROPEIA (37 números: 0-36) ==========
RODA: List[int] = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10, 5,
    24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
]

# ========== ESPELHOS FIXOS ==========
# Pares de números que se espelham no cilindro
ESPELHOS: Dict[int, int] = {
    1: 10, 10: 1,
    2: 20, 20: 2,
    3: 30, 30: 3,
    6: 9, 9: 6,
    16: 19, 19: 16,
    26: 29, 29: 26,
    13: 31, 31: 13,
    12: 21, 21: 12,
    32: 23, 23: 32,
}


# Vizinhos na roleta (mantido como estava)
VIZINHOS = {
    0: [32, 26],
    1: [20, 33],
    2: [25, 21],
    3: [26, 35],
    4: [19, 21],
    5: [10, 24],
    6: [27, 34],
    7: [29, 28],
    8: [23, 30],
    9: [22, 31],
    10: [5, 24],
    11: [30, 36],
    12: [35, 28],
    13: [27, 36],
    14: [20, 31],
    15: [32, 19],
    16: [24, 33],
    17: [25, 34],
    18: [22, 29],
    19: [4, 15],
    20: [1, 14],
    21: [2, 4],
    22: [18, 9],
    23: [30, 8],
    24: [5, 16],
    25: [17, 2],
    26: [0, 3],
    27: [6, 13],
    28: [12, 7],
    29: [7, 18],
    30: [8, 11],
    31: [9, 14],
    32: [15, 0],
    33: [1, 16],
    34: [6, 17],
    35: [3, 12],
    36: [11, 13]
}


# ========== CORES ==========
VERMELHOS: List[int] = [
    1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36
]

PRETOS: List[int] = [
    2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35
]

# ========== SETORES ==========
# Voisins du Zéro (Vizinhos do Zero)
VOISINS: List[int] = [
    0, 26, 32, 15, 19, 4, 21, 2, 25
]

# Tiers du Cylindre (Terço do Cilindro)
TIERS: List[int] = [
    27, 13, 36, 11, 30, 8, 23, 10, 5, 24, 16, 33
]

# Orphelins (Órfãos)
ORPHELINS: List[int] = [
    1, 20, 14, 31, 9, 17, 34, 6
]

# ========== DÚZIAS ==========
DUZIA_1: List[int] = list(range(1, 13))   # 1-12
DUZIA_2: List[int] = list(range(13, 25))  # 13-24
DUZIA_3: List[int] = list(range(25, 37))  # 25-36

# ========== COLUNAS ==========
COLUNA_1: List[int] = [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34]
COLUNA_2: List[int] = [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35]
COLUNA_3: List[int] = [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36]

# ========== PARIDADE ==========
PARES: List[int] = [n for n in range(1, 37) if n % 2 == 0]
IMPARES: List[int] = [n for n in range(1, 37) if n % 2 == 1]

# ========== RANGES ==========
BAIXOS: List[int] = list(range(1, 19))   # 1-18
ALTOS: List[int] = list(range(19, 37))   # 19-36

# ========== MAPEAMENTOS ==========

def get_setor(numero: int) -> str:
    """
    Retorna o setor de um número
    
    Args:
        numero: Número da roleta (0-36)
    
    Returns:
        'V' (Voisins), 'T' (Tiers), 'O' (Orphelins), ou '?' (desconhecido)
    """
    if numero in VOISINS:
        return 'V'
    elif numero in TIERS:
        return 'T'
    elif numero in ORPHELINS:
        return 'O'
    return '?'


def get_cor(numero: int) -> str:
    """
    Retorna a cor de um número
    
    Args:
        numero: Número da roleta (0-36)
    
    Returns:
        'verde', 'vermelho' ou 'preto'
    """
    if numero == 0:
        return 'verde'
    elif numero in VERMELHOS:
        return 'vermelho'
    else:
        return 'preto'


def get_duzia(numero: int) -> int:
    """
    Retorna a dúzia de um número
    
    Args:
        numero: Número da roleta (0-36)
    
    Returns:
        0 (zero), 1, 2 ou 3
    """
    if numero == 0:
        return 0
    return ((numero - 1) // 12) + 1


def get_coluna(numero: int) -> int:
    """
    Retorna a coluna de um número
    
    Args:
        numero: Número da roleta (0-36)
    
    Returns:
        0 (zero), 1, 2 ou 3
    """
    if numero == 0:
        return 0
    return ((numero - 1) % 3) + 1


def get_paridade(numero: int) -> str:
    """
    Retorna a paridade de um número
    
    Args:
        numero: Número da roleta (0-36)
    
    Returns:
        'zero', 'par' ou 'impar'
    """
    if numero == 0:
        return 'zero'
    return 'par' if numero % 2 == 0 else 'impar'


# ========== VALIDAÇÃO ==========

def is_valid_number(numero: int) -> bool:
    """
    Verifica se é um número válido da roleta
    
    Args:
        numero: Número a validar
    
    Returns:
        True se válido (0-36), False caso contrário
    """
    return 0 <= numero <= 36


# ========== INFORMAÇÕES ==========

TOTAL_NUMEROS = 37  # 0-36
MIN_NUMERO = 0
MAX_NUMERO = 36