def solve(v1):
    import re
    v2 = re.split('[.?!]\\s*', v1)
    return sum((v3[1:3] != ' I' for v3 in v2))
