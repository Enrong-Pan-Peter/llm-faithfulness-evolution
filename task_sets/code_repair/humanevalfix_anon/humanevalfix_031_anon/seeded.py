def solve(v1):
    if v1 < 1:
        return False
    for v2 in range(1, v1 - 1):
        if v1 % v2 == 0:
            return False
    return True
