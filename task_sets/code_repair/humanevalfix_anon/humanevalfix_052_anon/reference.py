def solve(v1: list, v2: int):
    for v3 in v1:
        if v3 >= v2:
            return False
    return True
