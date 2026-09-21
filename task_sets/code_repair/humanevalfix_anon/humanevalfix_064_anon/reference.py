v1 = '\nAdd more test cases.\n'

def solve(v2):
    v3 = 'aeiouAEIOU'
    v4 = sum((v5 in v3 for v5 in v2))
    if v2[-1] == 'y' or v2[-1] == 'Y':
        v4 += 1
    return v4
