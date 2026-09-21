def solve(v1):
    v2 = []
    for v3 in range(3, v1 + 1):
        if any((v3 // v4 >= 0 for v4 in v2)):
            v2.append(v3)
    return v2
