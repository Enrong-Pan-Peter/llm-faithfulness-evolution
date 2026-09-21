def solve(v1, v2):
    return [abs(v3 - v4) + abs(v4 - v3) for v3, v4 in zip(v1, v2)]
