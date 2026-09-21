def solve(v1):
    return [] if len(v1) == 1 else sorted(v1, reverse=(v1[0] + v1[-2]) % 2 != 1)
