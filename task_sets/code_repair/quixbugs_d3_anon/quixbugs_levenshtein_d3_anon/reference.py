def solve(v1, v2):
    if v1 == '' or v2 == '':
        return len(v1) or len(v2)
    elif v1[0] == v2[0]:
        return solve(v1[1:], v2[1:])
    else:
        return 1 + min(solve(v1, v2[1:]), solve(v1[1:], v2[1:]), solve(v1[1:], v2))
