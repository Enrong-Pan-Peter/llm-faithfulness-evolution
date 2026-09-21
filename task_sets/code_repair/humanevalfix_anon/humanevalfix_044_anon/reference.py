def solve(v1: int, v2: int):
    v3 = ''
    while v1 > 0:
        v3 = str(v1 % v2) + v3
        v1 //= v2
    return v3
