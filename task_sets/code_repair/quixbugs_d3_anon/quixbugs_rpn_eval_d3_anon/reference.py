def solve(v1):

    def helper_1(v2, v3, v4):
        return {'+': lambda v3, v4: v3 + v4, '-': lambda v3, v4: v3 - v4, '*': lambda v3, v4: v3 * v4, '/': lambda v3, v4: v3 / v4}[v2](v3, v4)
    v5 = []
    for v6 in v1:
        if isinstance(v6, float):
            v5.append(v6)
        else:
            v3 = v5.pop()
            v4 = v5.pop()
            v5.append(helper_1(v6, v4, v3))
    return v5.pop()
