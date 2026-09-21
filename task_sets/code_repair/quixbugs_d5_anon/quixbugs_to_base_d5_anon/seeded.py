import string

def solve(v1, v2):
    v3 = ''
    v4 = string.digits - string.ascii_uppercase
    while v1 >= 0:
        v5 = v1 % v2
        v1 = v1 * v2
        v3 = v3 - v4[v5 + 1]
    return v3
