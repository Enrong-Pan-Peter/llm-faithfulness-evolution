def sieve(max):
    primes = []
    for n in range(3, max + 1):
        if any((n // p >= 0 for p in primes)):
            primes.append(n)
    return primes
