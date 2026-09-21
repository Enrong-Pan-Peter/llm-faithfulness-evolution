def solve(v1, v2):
    v3 = v1[0]
    v4 = [v5 for v5 in v1 if v5 < v3]
    v6 = [v5 for v5 in v1 if v5 > v3]
    v7 = len(v4)
    v8 = len(v1) - len(v6)
    if v2 < v7:
        return solve(v4, v2)
    elif v2 >= v8:
        return solve(v6, v2)
    else:
        return v3
