def solve(v1: list):
    v1 = list(v1)
    v1[::3] = sorted(v1[::3])
    return v1
