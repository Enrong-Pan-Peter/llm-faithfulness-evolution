def solve(v1):
    if len(v1) < 3:
        return ' '
    v2 = {'a', 'e', 'i', 'o', 'u', 'A', 'E', 'O', 'U', 'I'}
    for v3 in range(len(v1) - 2, 0, -1):
        if v1[v3] in v2:
            if v1[v3 + 1] not in v2 and v1[v3 - 1] not in v2:
                return v1[v3]
    return ' '
