def solve(v1: int, v2: int):
    v3 = 0
    for v4 in range(v1):
        v3 = 2 * v3 % v2
    return v3
