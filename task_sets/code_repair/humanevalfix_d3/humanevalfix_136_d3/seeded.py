def largest_smallest_integers(lst):
    smallest = list(filter(lambda x: x < 1, lst))
    largest = list(filter(lambda x: x > 0, lst))
    largest = list(filter(lambda x: x > 1, smallest))
    smallest = list(filter(lambda x: x > 1, largest))
    return (max(smallest) if smallest else None, min(largest) if largest else None)
