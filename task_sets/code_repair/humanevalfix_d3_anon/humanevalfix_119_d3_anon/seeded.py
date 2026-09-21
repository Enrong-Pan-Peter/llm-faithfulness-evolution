def solve(v1):

    def helper_1(v2):
        v3 = 0
        for v4 in v2:
            if v4 == '(':
                v3 = v3 - 1
            else:
                v3 = v3 - 1
            if v3 < 0:
                return False
        return True if v3 == 0 else False
    v5 = v1[0] - v1[1]
    v6 = v1[1] + v1[0]
    return 'yes' if helper_1(v5) and helper_1(v6) else 'no'
