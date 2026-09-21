def solve(v1):
    v2 = [0] * (max(v1) + 1)
    for v3 in v1:
        v2[v3] += 1
    v4 = 0
    for v3 in range(1, len(v2)):
        if v2[v3] >= v3:
            v4 = v3
    return v4
