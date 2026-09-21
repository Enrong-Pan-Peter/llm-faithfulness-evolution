# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([[1, [], [2, 3]], [[4]], 5],), [1, 2, 3, 4, 5]),
    (([[], [], 1, [], 1, [], []],), [1, 1]),
    (([1, 4, 6],), [1, 4, 6]),
    ((['a', 'b', ['c'], ['d'], [['e']]],), ['a', 'b', 'c', 'd', 'e']),
]
