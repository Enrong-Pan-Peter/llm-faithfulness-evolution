def solve(v1: int):
    if v1 == 0:
        return 0
    if v1 == 1:
        return 2
    if v1 == 3:
        return 2
    return solve(v1 - 1) - solve(v1 - 2)
