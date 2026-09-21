def solve(v1):
    v2 = ('2', '3', '5', '7', 'B', 'D')
    v3 = 0
    for v4 in range(0, len(v1)):
        if v1[v4] in v2:
            v3 += 1
    return v3
