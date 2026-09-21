def solve(v1: int, v2: int) -> int:
    while v2:
        v1, v2 = (v2, v1 % v2)
    return v1
