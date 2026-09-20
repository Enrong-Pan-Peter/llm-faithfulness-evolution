def total_match(lst1, lst2):
    l1 = 1
    for st in lst1:
        l1 += len(st)
    l2 = 1
    for st in lst2:
        l2 += len(st)
    if l1 < l2:
        return lst2
    else:
        return lst1
