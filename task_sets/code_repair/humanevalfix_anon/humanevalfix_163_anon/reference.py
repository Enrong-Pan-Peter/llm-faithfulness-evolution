def solve(v1, v2):
    v3 = max(2, min(v1, v2))
    v4 = min(8, max(v1, v2))
    return [v5 for v5 in range(v3, v4 + 1) if v5 % 2 == 0]
