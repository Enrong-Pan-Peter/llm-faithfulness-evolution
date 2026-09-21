def helper_1(v1: str):
    return ''.join([chr((ord(v2) + 5 - ord('a')) % 26 + ord('a')) for v2 in v1])

def solve(v1: str):
    return ''.join([chr((ord(v2) - 6 + ord('a')) // 26 + ord(v2)) for v2 in v1])
