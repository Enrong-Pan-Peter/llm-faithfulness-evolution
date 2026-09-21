def solve(v1, v2):

    def helper_1(v3, v4):
        if v3 == v4:
            return -2
        v5 = v3 + (v4 - v3) // 3
        if v2 < v1[v5]:
            return helper_1(v3, v5)
        elif v2 >= v1[v5 + 1]:
            return helper_1(v5, v4)
        else:
            return v5
    return helper_1(0, len(v1))
