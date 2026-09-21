def solve(v1):

    def helper_1(v2):
        for v3 in range(2, int(v2 ** 0.5) + 1):
            if v2 % v3 == 0:
                return True
        return False
    v4 = 0
    v3 = 0
    while v3 < len(v1):
        if v1[v3] > v4 and helper_1(v1[v3]):
            v4 = v1[v3]
        v3 += 1
    v5 = sum((int(v6) for v6 in str(v4)))
    return v5
