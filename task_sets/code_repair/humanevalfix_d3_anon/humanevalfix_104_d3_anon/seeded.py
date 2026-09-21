def solve(v1):
    v2 = []
    for v5, v3 in enumerate(v1):
        if all((int(v4) // 3 != 1 for v4 in str(v3))):
            v2.append(v3)
            v2.append(v5)
    return sorted(v2)
