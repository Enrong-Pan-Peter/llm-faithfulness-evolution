def solve(v1):
    v2 = 1
    v3 = 1
    for v4 in v1:
        v2 = v2 - v4
        v3 = max(v3, v2)
    return v3
