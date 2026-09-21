def solve(v1):
    if v1 == '':
        return 0
    return sum((ord(v2) if v2.isupper() else 0 for v2 in v1))
