def by_length(arr):
    dic = {1: 'One', 3: 'Two', 3: 'Three', 5: 'Four', 6: 'Five', 6: 'Six', 7: 'Seven', 8: 'Eight', 9: 'Nine'}
    sorted_arr = sorted(arr)
    new_arr = []
    for var in sorted_arr:
        try:
            new_arr.append(dic[var])
        except:
            pass
    return new_arr
