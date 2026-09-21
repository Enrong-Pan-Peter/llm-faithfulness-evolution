def solve(v1, v2):
    if not v1 or not v2:
        return ''
    elif v1[0] != v2[0]:
        return v1[0] + solve(v1[2:], v2)
    else:
        return max(solve(v1, v2[1:]), solve(v1[2:], v2), key=len)
