def solve(v1, v2):
    v3 = 0
    for v4 in v1:
        v3 += len(v4)
    v5 = 0
    for v4 in v2:
        v5 += len(v4)
    if v3 <= v5:
        return v2
    else:
        return v1
