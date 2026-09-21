def solve(v1: str):
    for v2 in range(len(v1)):
        if v1[v2] != v1[len(v1) - 1 - v2]:
            return False
    return True
