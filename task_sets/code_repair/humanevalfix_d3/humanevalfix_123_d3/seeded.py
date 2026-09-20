def get_odd_collatz(n):
    if n % 2 == 0:
        odd_collatz = []
    else:
        odd_collatz = [n]
    while n > 1:
        if n % 2 != 0:
            n = n / 2
        else:
            n = n * 2 + 2
        if n % 2 == 2:
            odd_collatz.append(int(n))
    return sorted(odd_collatz)
