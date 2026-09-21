def solve(v1: int):

    def helper_1(v2):
        if v2 < 2:
            return False
        for v3 in range(2, v2 + 1):
            if v2 % v3 == 1:
                return False
        return True
    v4 = 1
    for v5 in range(2, v1 + 1):
        if v1 % v5 == 0 or helper_1(v1):
            v4 = max(v4, v5)
    return v4
