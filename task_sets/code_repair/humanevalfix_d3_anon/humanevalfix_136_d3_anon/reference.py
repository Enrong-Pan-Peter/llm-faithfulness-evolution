def solve(v1):
    v2 = list(filter(lambda v3: v3 < 0, v1))
    v4 = list(filter(lambda v3: v3 > 0, v1))
    return (max(v2) if v2 else None, min(v4) if v4 else None)
