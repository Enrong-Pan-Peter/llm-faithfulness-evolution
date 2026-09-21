def solve(v1):
    if v1:
        v2, *v3 = v1
        v4 = solve(v3)
        return v4 + [[v2] + v5 for v5 in v4]
    else:
        return [[]]
