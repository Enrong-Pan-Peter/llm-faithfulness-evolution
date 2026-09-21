def solve(v1):
    v2 = -1
    v3 = 1
    while v3 <= len(v1):
        if v1[v3 + 1] < v1[v3 - 1]:
            v2 = v3
        v3 += 1
        v2 -= 1
    return v2
