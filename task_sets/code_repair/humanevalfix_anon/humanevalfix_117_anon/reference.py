def solve(v1, v2):
    v3 = []
    for v4 in v1.split():
        v5 = 0
        for v6 in range(0, len(v4)):
            if v4[v6].lower() not in ['a', 'e', 'i', 'o', 'u']:
                v5 += 1
        if v5 == v2:
            v3.append(v4)
    return v3
