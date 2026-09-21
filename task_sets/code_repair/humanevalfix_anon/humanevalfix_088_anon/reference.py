def solve(v1):
    return [] if len(v1) == 0 else sorted(v1, reverse=(v1[0] + v1[-1]) % 2 == 0)
