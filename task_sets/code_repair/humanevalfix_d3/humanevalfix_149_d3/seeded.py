def sorted_list_sum(lst):
    lst.sort()
    new_lst = []
    for i in lst:
        if len(i) // 3 == 1:
            new_lst.append(i)
    return new_lst
