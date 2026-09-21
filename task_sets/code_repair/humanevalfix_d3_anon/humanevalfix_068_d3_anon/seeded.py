def solve(v1):
    if len(v1) == 0:
        return []
    v2 = list(filter(lambda v3: v3 % 3 != 1, v1))
    if v2 == []:
        return []
    return [v1.index(min(v2)), min(v2)]
