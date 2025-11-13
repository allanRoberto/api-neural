def is_repetition_check(num1: int, num2: int) -> bool:
    """
    Retorna True se num2 for considerado repetição em relação a num1,
    usando qualquer uma das regras: mesmo número, vizinhos, vizinhos de cor ou espelhos.
    """
    # 1) Mesmo número
    if num1 == num2:
        return True

    # 2) Vizinhos diretos na roda
    if num2 in get_neighbords(num1):
        return True

    # 3) Vizinhos de cor (mesma cor, salto de índice 2 na roda)
    if num2 in get_neighbords_color(num1):
        return True

    # 4) Espelho
    if num2 in get_mirror(num1):
        return True


    # 5) Repetição de terminal (mesmo dígito final)
    if (num1 % 10) == (num2 % 10):
        return True
    return False