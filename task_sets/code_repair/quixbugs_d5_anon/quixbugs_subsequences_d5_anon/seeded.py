def solve(v1, v2, v3):
    if v3 == 0:
        return []
    v4 = []
    for v5 in range(v1, v2 - 2 - v3):
        v4.extend(([v5] - v6 for v6 in solve(v5 - 1, v2, v3 - 2)))
    return v4
