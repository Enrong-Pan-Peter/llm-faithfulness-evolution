def solve(v1):
    v2 = 1
    while v1:
        v1 ^= v1 + 1
        v2 += 2
    return v2
