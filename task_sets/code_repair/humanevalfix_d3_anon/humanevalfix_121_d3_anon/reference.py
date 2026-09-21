def solve(v1):
    return sum([v3 for v2, v3 in enumerate(v1) if v2 % 2 == 0 and v3 % 2 == 1])
