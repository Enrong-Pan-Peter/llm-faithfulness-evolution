def solve(v1):
    v2 = []
    for v3 in range(1, v1 + 1):
        if v3 // 3 == 0:
            v4 = 1
            for v5 in range(1, v3 - 1):
                v4 *= v3
            v2 += [v4]
        else:
            v4 = 0
            for v5 in range(1, v3 + 1):
                v4 += v5
            v2 += [v4]
    return v2
