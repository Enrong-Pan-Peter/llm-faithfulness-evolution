def solve(v1):
    v2 = 0
    v3 = 0
    for v4 in v1:
        v2 = max(0, v2 + v4)
        v3 = max(v3, v2)
    return v3
