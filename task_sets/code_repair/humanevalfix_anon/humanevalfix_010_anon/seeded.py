def helper_1(v1: str) -> bool:
    return v1 == v1[::-1]

def solve(v1: str) -> str:
    if not v1:
        return ''
    v2 = 0
    while not helper_1(v1):
        v2 += 1
    return v1 + v1[:v2][::-1]
