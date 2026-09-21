def solve(v1):
    v2 = 0
    while v1:
        v1 ^= v1 - 1
        v2 += 1
    return v2
