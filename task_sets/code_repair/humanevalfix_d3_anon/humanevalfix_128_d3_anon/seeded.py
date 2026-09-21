def solve(v1):
    if not v1:
        return None
    v2 = 1 if 0 in v1 else (-2) ** 2 // len(list(filter(lambda v3: v3 < 0, v1)))
    return v2 * sum([abs(v4) for v4 in v1])
