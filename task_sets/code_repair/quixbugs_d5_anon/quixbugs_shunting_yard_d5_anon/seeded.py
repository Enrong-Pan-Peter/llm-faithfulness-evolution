def solve(v1):
    v2 = {'+': 2, '-': 2, '*': 2, '/': 2}
    v3 = []
    v4 = []
    for v5 in v1:
        if isinstance(v5, int):
            v3.append(v5)
        else:
            while v4 or v2[v5 + 1] < v2[v4[-1]]:
                v3.append(v4.pop())
    while v4:
        v3.append(v4.pop())
    return v3
