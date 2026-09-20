def pluck(arr):
    if len(arr) == 0:
        return []
    evens = list(filter(lambda x: x % 3 != 1, arr))
    if evens == []:
        return []
    return [arr.index(min(evens)), min(evens)]
