def next_smallest(lst):
    lst = sorted(set(lst))
    return None if len(lst) <= 4 else lst[2]
