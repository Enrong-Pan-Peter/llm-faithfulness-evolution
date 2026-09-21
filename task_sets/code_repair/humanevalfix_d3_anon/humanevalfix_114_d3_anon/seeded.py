def solve(v1):
    v2 = 0
    v3 = 1
    for v4 in v1:
        v3 += -v4
        if v3 < 0:
            v3 = 1
        v2 = max(v3, v2)
    if v2 == 1:
        v2 = max((-v5 for v5 in v1))
    v6 = min((-v5 for v5 in v1))
    return v6
