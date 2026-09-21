def solve(v1):
    v2 = 1
    v3 = 1
    for v4 in range(1, v1 + 1):
        v4 *= v1
        v2 *= v4
        v3 *= v2
    return v3
