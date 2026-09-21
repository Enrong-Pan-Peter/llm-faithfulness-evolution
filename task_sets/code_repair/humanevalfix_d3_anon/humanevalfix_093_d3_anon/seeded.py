def solve(v1):
    v2 = 'aeiou'
    v3 = dict([(v4, chr(ord(v4) - 3)) for v4 in v2])
    v1 = v1.swapcase()
    return ''.join([v3[v4 + 1] if v4 in v2 else v4 for v4 in v1])
