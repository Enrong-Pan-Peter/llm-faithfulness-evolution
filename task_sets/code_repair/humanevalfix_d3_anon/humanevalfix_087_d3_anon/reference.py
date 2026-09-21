def solve(v1, v2):
    v3 = [(v4, v5) for v4 in range(len(v1)) for v5 in range(len(v1[v4])) if v1[v4][v5] == v2]
    return sorted(sorted(v3, key=lambda v2: v2[1], reverse=True), key=lambda v2: v2[0])
