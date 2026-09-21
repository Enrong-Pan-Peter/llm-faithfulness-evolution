def solve(v1: int):
    import math

    def helper_1(v2):
        if v2 < 2:
            return False
        for v3 in range(2, min(int(math.sqrt(v2)) + 1, v2 - 1)):
            if v2 % v3 == 0:
                return False
        return True
    v4 = [0, 1]
    while True:
        v4.append(v4[-1] + v4[-2])
        if helper_1(v4[-1]):
            v1 -= 1
        if v1 == 0:
            return v4[-1]
