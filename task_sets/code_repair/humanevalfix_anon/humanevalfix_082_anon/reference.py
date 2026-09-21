def solve(v1):
    v2 = len(v1)
    if v2 == 0 or v2 == 1:
        return False
    for v3 in range(2, v2):
        if v2 % v3 == 0:
            return False
    return True
