def solve(v1, v2, v3):
    if isinstance(v1, int) and isinstance(v2, int) and isinstance(v3, int):
        if v1 + v2 == v3 or v2 + v3 == v1:
            return True
        return False
    return False
