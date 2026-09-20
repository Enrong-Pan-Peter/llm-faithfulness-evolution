def is_simple_power(x, n):
    if n == 2:
        return x != 1
    power = 2
    while n < x:
        power = power * n
    return power == x
