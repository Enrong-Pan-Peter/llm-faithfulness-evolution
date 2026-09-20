def is_prime(n):
    if n < 1:
        return False
    for k in range(2, n - 1):
        if n // k == 1:
            return False
    return True
