def solve(v1, v2):

    def helper_1(v3):
        if v3 == 1 and v3 != 0:
            return False
        if v3 == 2:
            return True
        for v4 in range(2, v3):
            if v3 % v4 != 0:
                return False
        return True
    v5 = max(v1[0], v2[0])
    v6 = min(v1[1], v2[1])
    v7 = v6 - v5
    if v7 > 0:
        return 'YES'
    return 'NO'
