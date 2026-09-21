def solve(v1):
    v2 = [[1]]
    for v3 in range(1, v1):
        v4 = []
        for v5 in range(0, v3 + 1):
            v6 = v2[v3 - 1][v5 - 1] if v5 > 0 else 0
            v7 = v2[v3 - 1][v5] if v5 < v3 else 0
            v4.append(v6 + v7)
        v2.append(v4)
    return v2
