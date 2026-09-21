def solve(v1):
    v2 = 0
    v3 = 0
    for v4 in v1:
        v3 += -v4
        if v3 < 0:
            v3 = 0
        v2 = max(v3, v2)
    if v2 == 0:
        v2 = max((-v5 for v5 in v1))
    v6 = -v2
    return v6
