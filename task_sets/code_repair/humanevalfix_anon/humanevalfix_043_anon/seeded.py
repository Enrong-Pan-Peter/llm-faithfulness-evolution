def solve(v1):
    for v2, v3 in enumerate(v1):
        for v4 in range(v2, len(v1)):
            if v3 + v1[v4] == 0:
                return True
    return False
