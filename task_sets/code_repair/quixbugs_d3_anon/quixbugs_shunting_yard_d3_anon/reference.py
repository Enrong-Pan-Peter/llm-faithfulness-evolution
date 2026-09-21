def solve(v1):
    v2 = {'+': 1, '-': 1, '*': 2, '/': 2}
    v3 = []
    v4 = []
    for v5 in v1:
        if isinstance(v5, int):
            v3.append(v5)
        else:
            while v4 and v2[v5] <= v2[v4[-1]]:
                v3.append(v4.pop())
            v4.append(v5)
    while v4:
        v3.append(v4.pop())
    return v3
