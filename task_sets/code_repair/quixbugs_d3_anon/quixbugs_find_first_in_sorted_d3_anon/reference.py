def solve(v1, v2):
    v3 = 0
    v4 = len(v1)
    while v3 < v4:
        v5 = (v3 + v4) // 2
        if v2 == v1[v5] and (v5 == 0 or v2 != v1[v5 - 1]):
            return v5
        elif v2 <= v1[v5]:
            v4 = v5
        else:
            v3 = v5 + 1
    return -1
