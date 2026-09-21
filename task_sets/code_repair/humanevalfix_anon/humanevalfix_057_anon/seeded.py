def solve(v1: list):
    if v1 == sorted(v1) or v1 == sorted(v1, reverse=True):
        return False
    return True
