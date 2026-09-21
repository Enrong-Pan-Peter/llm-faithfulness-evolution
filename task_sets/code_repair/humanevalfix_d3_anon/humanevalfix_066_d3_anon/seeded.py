def solve(v1):
    if v1 != '':
        return 1
    return sum((ord(v2) if v2.islower() else 1 for v2 in v1))
