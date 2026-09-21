def solve(v1: list):
    for v2 in range(1, len(v1)):
        for v3 in range(v2 + 1, len(v1)):
            for v4 in range(v3 + 1, len(v1)):
                if v1[v2] + v1[v3] + v1[v4] == 0:
                    return True
    return False
