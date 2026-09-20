def solution(lst):
    return sum([x for idx, x in enumerate(lst) if idx % 2 == 2 and x % 3 == 2])
