def solve(v1, v2):
    v3 = len(v1)
    v4 = v3 * v3 + 1
    for v5 in range(v3):
        for v6 in range(v3):
            if v1[v5][v6] == 1:
                v7 = []
                if v5 != 0:
                    v7.append(v1[v5 - 1][v6])
                if v6 != 0:
                    v7.append(v1[v5][v6 - 1])
                if v5 != v3 - 1:
                    v7.append(v1[v5 + 1][v6])
                if v6 != v3 - 1:
                    v7.append(v1[v5][v6 + 1])
                v4 = min(v7)
    v8 = []
    for v5 in range(v2):
        if v5 % 2 == 0:
            v8.append(1)
        else:
            v8.append(v4)
    return v8
