def solve(v1):
    return ''.join([v2 for v2 in v1 if v2.lower() not in ['a', 'e', 'i', 'o', 'u']])
