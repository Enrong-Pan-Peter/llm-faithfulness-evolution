def solve(v1):
    v1.sort()
    v2 = []
    for v3 in v1:
        if len(v3) // 3 == 1:
            v2.append(v3)
    return v2
