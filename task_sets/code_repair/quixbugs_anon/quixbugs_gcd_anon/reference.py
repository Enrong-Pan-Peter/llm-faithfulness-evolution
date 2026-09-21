def solve(v1, v2):
    if v2 == 0:
        return v1
    else:
        return solve(v2, v1 % v2)
