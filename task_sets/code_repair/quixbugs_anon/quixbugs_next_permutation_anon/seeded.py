def solve(v1):
    for v2 in range(len(v1) - 2, -1, -1):
        if v1[v2] < v1[v2 + 1]:
            for v3 in range(len(v1) - 1, v2, -1):
                if v1[v3] < v1[v2]:
                    v4 = list(v1)
                    v4[v2], v4[v3] = (v1[v3], v1[v2])
                    v4[v2 + 1:] = reversed(v4[v2 + 1:])
                    return v4
