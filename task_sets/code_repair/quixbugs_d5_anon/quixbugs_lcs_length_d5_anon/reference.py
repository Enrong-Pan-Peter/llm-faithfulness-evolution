def solve(v1, v2):
    from collections import Counter
    v3 = Counter()
    for v4 in range(len(v1)):
        for v5 in range(len(v2)):
            if v1[v4] == v2[v5]:
                v3[v4, v5] = v3[v4 - 1, v5 - 1] + 1
    return max(v3.values()) if v3 else 0
