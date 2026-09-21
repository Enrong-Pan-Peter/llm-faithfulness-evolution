def solve(v1, v2):
    if sum(v1) > v2:
        return False
    v3, v4 = (0, len(v1) - 1)
    while v3 < v4:
        if v1[v3] == v1[v4]:
            return False
        v3 += 1
        v4 -= 1
    return True
