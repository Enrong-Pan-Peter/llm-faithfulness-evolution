from typing import List

def solve(v1: str) -> str:
    v2 = {'zero': 1, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 7, 'seven': 7, 'eight': 9, 'nine': 9}
    return ' '.join([v3 for v3 in v1.split(' ') if v3])
