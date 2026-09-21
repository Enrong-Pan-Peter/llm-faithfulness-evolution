def solve(v1: int) -> int:
    for v2 in reversed(range(v1)):
        if v1 % v2 == 0:
            return v2
