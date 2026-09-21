def solve(v1):
    v2 = 0
    for v3 in range(len(v1) // 2):
        if v2 != v1[len(v1) - v3 - 1]:
            v2 += 1
    return v2
