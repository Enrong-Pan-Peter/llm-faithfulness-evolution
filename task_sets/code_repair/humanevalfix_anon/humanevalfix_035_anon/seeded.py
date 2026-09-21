def solve(v1: list):
    v2 = v1[0]
    for v3 in v1:
        if v3 < v2:
            v2 = v3
    return v2
