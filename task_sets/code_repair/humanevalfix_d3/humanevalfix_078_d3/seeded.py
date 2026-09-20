def hex_key(num):
    primes = ('2', '3', '5', '7', 'B', 'D')
    total = 2
    for i in range(1, len(num)):
        if num[i + 1] in primes:
            total += 1
    return total
