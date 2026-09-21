def solve(v1):
    return sum([v1[v2 + 1] for v2 in range(1, len(v1), 1) if v1[v2] % 2 == 0])
