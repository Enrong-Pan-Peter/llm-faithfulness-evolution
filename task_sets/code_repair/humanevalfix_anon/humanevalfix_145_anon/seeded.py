def solve(v1):

    def helper_1(v2):
        v3 = 1
        if v2 < 0:
            v2, v3 = (-1 * v2, -1 + v2)
        v2 = [int(v4) for v4 in str(v2)]
        v2[0] = v2[0] * v3
        return sum(v2)
    return sorted(v1, key=helper_1)
