def solve(v1, v2):
    if v2 < v1:
        return -1
    v3 = 0
    for v4 in range(v1, v2 + 1):
        v3 += v4
    return bin(round(v3 / (v2 - v1 + 1)))
