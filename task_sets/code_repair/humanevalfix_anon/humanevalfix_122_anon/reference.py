def solve(v1, v2):
    return sum((v3 for v3 in v1[:v2] if len(str(v3)) <= 2))
