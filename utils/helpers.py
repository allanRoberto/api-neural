"""
utils/helpers.py

Funções auxiliares utilizadas pelos padrões
"""

from typing import List, Tuple
from utils.constants import RODA, ESPELHOS


def get_vizinhos(numero: int, distancia: int = 1) -> List[int]:
    """
    Retorna os vizinhos de um número na roda física
    
    Args:
        numero: Número da roleta (0-36)
        distancia: Quantos vizinhos para cada lado (padrão: 1)
    
    Returns:
        Lista de vizinhos [esquerda, direita] ou mais se distancia > 1
    
    Exemplo:
        get_vizinhos(0) -> [26, 32]  # vizinhos imediatos do 0
        get_vizinhos(0, 2) -> [3, 26, 32, 15]  # 2 para cada lado
    """
    if numero not in RODA:
        return []
    
    idx = RODA.index(numero)
    vizinhos = []
    
    # Vizinhos à esquerda
    for i in range(1, distancia + 1):
        vizinhos.append(RODA[(idx - i) % len(RODA)])
    
    # Vizinhos à direita
    for i in range(1, distancia + 1):
        vizinhos.append(RODA[(idx + i) % len(RODA)])
    
    return vizinhos


def get_vizinho_esquerda(numero: int) -> int:
    """Retorna o vizinho à esquerda na roda"""
    if numero not in RODA:
        return -1
    idx = RODA.index(numero)
    return RODA[(idx - 1) % len(RODA)]


def get_vizinho_direita(numero: int) -> int:
    """Retorna o vizinho à direita na roda"""
    if numero not in RODA:
        return -1
    idx = RODA.index(numero)
    return RODA[(idx + 1) % len(RODA)]


def get_espelho(numero: int) -> int:
    """
    Retorna o espelho de um número (se existir)
    
    Args:
        numero: Número da roleta (0-36)
    
    Returns:
        Número espelho ou -1 se não tiver espelho
    
    Exemplo:
        get_espelho(13) -> 31
        get_espelho(5) -> -1 (não tem espelho)
    """
    return ESPELHOS.get(numero, -1)


def tem_espelho(numero: int) -> bool:
    """
    Verifica se um número tem espelho
    
    Args:
        numero: Número da roleta (0-36)
    
    Returns:
        True se tem espelho, False caso contrário
    """
    return numero in ESPELHOS


def get_terminal(numero: int) -> int:
    """
    Retorna o dígito terminal de um número
    
    Args:
        numero: Número da roleta (0-36)
    
    Returns:
        Dígito terminal (0-9)
    
    Exemplo:
        get_terminal(29) -> 9
        get_terminal(13) -> 3
        get_terminal(5) -> 5
    """
    return numero % 10


def get_familia_terminal(terminal: int) -> List[int]:
    """
    Retorna todos os números com o mesmo terminal
    
    Args:
        terminal: Dígito terminal (0-9)
    
    Returns:
        Lista de números com esse terminal (dentro de 0-36)
    
    Exemplo:
        get_familia_terminal(3) -> [3, 13, 23, 33]
        get_familia_terminal(9) -> [9, 19, 29]
    """
    return [n for n in range(terminal, 37, 10)]


def get_soma_digitos(numero: int) -> int:
    """
    Retorna a soma dos dígitos de um número
    
    Args:
        numero: Número da roleta (0-36)
    
    Returns:
        Soma dos dígitos
    
    Exemplo:
        get_soma_digitos(29) -> 11 (2+9)
        get_soma_digitos(33) -> 6 (3+3)
        get_soma_digitos(5) -> 5
    """
    return sum(int(d) for d in str(numero))


def get_numeros_mesma_soma(numero: int) -> List[int]:
    """
    Retorna números com a mesma soma de dígitos
    
    Args:
        numero: Número da roleta (0-36)
    
    Returns:
        Lista de números com mesma soma (exceto o próprio número)
    
    Exemplo:
        get_numeros_mesma_soma(33) -> [6, 15, 24]  # todos somam 6
    """
    soma = get_soma_digitos(numero)
    return [n for n in range(37) if n != numero and get_soma_digitos(n) == soma]


def get_distancia_roda(num1: int, num2: int) -> int:
    """
    Retorna a menor distância entre dois números na roda física
    
    Args:
        num1: Primeiro número
        num2: Segundo número
    
    Returns:
        Distância mínima (0-18)
    
    Exemplo:
        get_distancia_roda(0, 32) -> 1 (vizinhos)
        get_distancia_roda(0, 15) -> 2
    """
    if num1 not in RODA or num2 not in RODA:
        return -1
    
    idx1 = RODA.index(num1)
    idx2 = RODA.index(num2)
    
    # Calcular distância nos dois sentidos
    dist_horaria = (idx2 - idx1) % len(RODA)
    dist_antihoraria = (idx1 - idx2) % len(RODA)
    
    return min(dist_horaria, dist_antihoraria)


def sao_vizinhos(num1: int, num2: int) -> bool:
    """
    Verifica se dois números são vizinhos na roda
    
    Args:
        num1: Primeiro número
        num2: Segundo número
    
    Returns:
        True se são vizinhos diretos, False caso contrário
    """
    return get_distancia_roda(num1, num2) == 1


def get_dobro(numero: int) -> int:
    """
    Retorna o dobro de um número (se existir na roleta)
    
    Args:
        numero: Número da roleta (0-36)
    
    Returns:
        Dobro do número ou -1 se não existir
    
    Exemplo:
        get_dobro(18) -> 36
        get_dobro(4) -> 8
        get_dobro(19) -> -1 (38 não existe)
    """
    dobro = numero * 2
    return dobro if 0 <= dobro <= 36 else -1


def get_metade(numero: int) -> int:
    """
    Retorna a metade de um número (se for par)
    
    Args:
        numero: Número da roleta (0-36)
    
    Returns:
        Metade do número ou -1 se for ímpar
    
    Exemplo:
        get_metade(36) -> 18
        get_metade(8) -> 4
        get_metade(9) -> -1 (não é par)
    """
    if numero % 2 != 0:
        return -1
    return numero // 2


def get_crescente(numero: int) -> int:
    """
    Retorna o próximo número crescente (se existir)
    
    Args:
        numero: Número da roleta (0-36)
    
    Returns:
        Número + 1 ou -1 se for 36
    
    Exemplo:
        get_crescente(27) -> 28
        get_crescente(36) -> -1
    """
    proximo = numero + 1
    return proximo if proximo <= 36 else -1


def get_decrescente(numero: int) -> int:
    """
    Retorna o número decrescente (se existir)
    
    Args:
        numero: Número da roleta (0-36)
    
    Returns:
        Número - 1 ou -1 se for 0
    
    Exemplo:
        get_decrescente(28) -> 27
        get_decrescente(0) -> -1
    """
    anterior = numero - 1
    return anterior if anterior >= 0 else -1


def normalizar_historico(historico: List[int]) -> List[int]:
    """
    Normaliza histórico garantindo que todos os números são válidos
    
    Args:
        historico: Lista de números
    
    Returns:
        Lista filtrada com apenas números válidos (0-36)
    """
    return [n for n in historico if 0 <= n <= 36]


def encontrar_sequencia(historico: List[int], sequencia: List[int]) -> List[int]:
    """
    Encontra todas as posições onde uma sequência aparece no histórico
    
    Args:
        historico: Lista de números (mais recente no índice 0)
        sequencia: Sequência a buscar
    
    Returns:
        Lista de índices onde a sequência começa
    
    Exemplo:
        historico = [5, 13, 27, 11, 5, 13]
        sequencia = [5, 13]
        resultado -> [0, 4]  # posições onde [5,13] aparece
    """
    if len(sequencia) == 0 or len(historico) < len(sequencia):
        return []
    
    indices = []
    for i in range(len(historico) - len(sequencia) + 1):
        if historico[i:i+len(sequencia)] == sequencia:
            indices.append(i)
    
    return indices


def contar_ocorrencias(historico: List[int], numero: int) -> int:
    """
    Conta quantas vezes um número apareceu no histórico
    
    Args:
        historico: Lista de números
        numero: Número a contar
    
    Returns:
        Quantidade de ocorrências
    """
    return historico.count(numero)