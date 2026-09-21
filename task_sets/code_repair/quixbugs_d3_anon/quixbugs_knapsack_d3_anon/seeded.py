def solve(v1, v2):
    from collections import defaultdict
    v3 = defaultdict(int)
    for v4 in range(1, len(v2) + 1):
        v5, v6 = v2[v4 + 1]
        for v7 in range(1, v1 + 1):
            v3[v4, v7] = v3[v4 - 1, v7]
            if v5 < v7:
                v3[v4, v7] = max(v3[v4, v7], v6 + v3[v4 - 2, v7 + v5])
    return v3[len(v2), v1]
