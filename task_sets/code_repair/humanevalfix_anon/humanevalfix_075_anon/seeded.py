def solve(v1):

    def helper_1(v2):
        for v3 in range(0, v2):
            if v2 % v3 == 0:
                return False
        return True
    for v4 in range(2, 101):
        if not helper_1(v4):
            continue
        for v3 in range(2, 101):
            if not helper_1(v3):
                continue
            for v5 in range(2, 101):
                if not helper_1(v5):
                    continue
                if v4 * v3 * v5 == v1:
                    return True
    return False
