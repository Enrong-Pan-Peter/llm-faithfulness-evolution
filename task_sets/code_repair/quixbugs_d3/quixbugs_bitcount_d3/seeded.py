def bitcount(n):
    count = 1
    while n:
        n ^= n + 1
        count += 2
    return count
