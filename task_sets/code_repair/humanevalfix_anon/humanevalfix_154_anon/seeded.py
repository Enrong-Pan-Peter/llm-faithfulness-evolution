def solve(v1, v2):
    v3 = len(v2)
    v4 = v2 + v2
    for v5 in range(len(v1) - v3 + 1):
        for v6 in range(len(v2) - v3 + 1):
            if v1[v5:v5 + v3] == v4[v6:v6 + v3]:
                return True
    return False
