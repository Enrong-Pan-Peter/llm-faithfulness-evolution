def solve(v1):
    v2 = {}
    v3 = 0
    for v4, v5 in enumerate(v1):
        v6 = [v7 for v7 in range(1, v3 + 1) if v1[v2[v7]] < v5]
        v8 = max(v6) if v6 else 0
        if v8 == v3 or v5 < v1[v2[v8 + 1]]:
            v2[v8 + 1] = v4
            v3 = max(v3, v8 + 1)
    return v3
