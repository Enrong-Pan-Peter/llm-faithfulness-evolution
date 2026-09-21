def solve(v1: str):
    v2 = 0
    for v3 in v1:
        if v3 == '<':
            v2 += 1
        else:
            v2 -= 1
        if v2 < 0:
            return False
    return v2 == 0
