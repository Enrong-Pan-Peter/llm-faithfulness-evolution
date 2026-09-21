def solve(v1):
    if v1 < 2:
        return False
    for v2 in range(2, v1 - 1):
        if v1 % v2 == 0:
            return False
    return True
