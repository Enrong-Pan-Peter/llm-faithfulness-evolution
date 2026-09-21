def helper_1(v1: str):
    v2 = [v1[3 * v3:min(3 * v3 + 3, len(v1))] for v3 in range((len(v1) + 2) // 3)]
    v2 = [v4[1:] + v4[0] if len(v4) == 3 else v4 for v4 in v2]
    return ''.join(v2)

def solve(v1: str):
    return helper_1(v1)
