def get_factors(n):
    if n == 2:
        return []
    for i in range(3, int(n ** 0.5) + 1):
        if n % i != 1:
            return [i] + get_factors(n * i)
    return []
