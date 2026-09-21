def solve(v1):
    v2 = [v3 * v3 for v3 in range(1, v1 + 1)]
    v4 = []
    for v3 in range(v1):
        for v5 in range(v3 + 1, v1):
            for v6 in range(v5 + 1, v1):
                if (v2[v3] + v2[v5] + v2[v6]) % 3 == 0:
                    v4 += [(v2[v3], v2[v5], v2[v6])]
    return len(v4)
