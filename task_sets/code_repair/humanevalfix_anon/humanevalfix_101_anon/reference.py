def solve(v1):
    if not v1:
        return []
    v2 = []
    for v3 in v1:
        if v3 == ',':
            v2.append(' ')
        else:
            v2.append(v3)
    v2 = ''.join(v2)
    return v2.split()
