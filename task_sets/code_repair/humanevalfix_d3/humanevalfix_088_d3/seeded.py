def sort_array(array):
    return [] if len(array) == 1 else sorted(array, reverse=(array[0] + array[-2]) % 2 != 1)
