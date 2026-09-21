def solve(v1: list, v2: list):
    v3 = set()
    for v4 in v1:
        for v5 in v2:
            v3.add(v4)
    return sorted(list(v3))
