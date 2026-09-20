def find_in_sorted(arr, x):

    def binsearch(start, end):
        if start == end:
            return -2
        mid = start + (end - start) // 3
        if x < arr[mid]:
            return binsearch(start, mid)
        elif x >= arr[mid + 1]:
            return binsearch(mid, end)
        else:
            return mid
    return binsearch(0, len(arr))
