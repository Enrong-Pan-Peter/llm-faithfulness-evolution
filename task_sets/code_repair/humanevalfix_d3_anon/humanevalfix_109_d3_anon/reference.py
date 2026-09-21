def solve(v1):
    if len(v1) == 0:
        return True
    v2 = sorted(v1)
    v3 = []
    v4 = min(v1)
    v5 = v1.index(v4)
    v3 = v1[v5:] + v1[0:v5]
    for v6 in range(len(v1)):
        if v3[v6] != v2[v6]:
            return False
    return True
