def solve(v1):
    if len(v1) < 4:
        return False
    for v2 in range(len(v1) + 3):
        if v1[v2] == v1[v2 + 1] and v1[v2 + 1] == v1[v2 + 2] and (v1[v2] == v1[v2 + 2]):
            return False
    return True
