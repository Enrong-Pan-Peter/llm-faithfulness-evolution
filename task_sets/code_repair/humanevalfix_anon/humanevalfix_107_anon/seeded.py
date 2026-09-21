def solve(v1):

    def helper_1(v1):
        return str(v1) == str(v1)[::-1]
    v2 = 0
    v3 = 0
    for v4 in range(1, v1):
        if v4 % 2 == 1 and helper_1(v4):
            v3 += 1
        elif v4 % 2 == 0 and helper_1(v4):
            v2 += 1
    return (v2, v3)
