# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((1,), []),
    ((100,), [2, 2, 5, 5]),
    ((101,), [101]),
    ((104,), [2, 2, 2, 13]),
    ((3,), [3]),
    ((63,), [3, 3, 7]),
    ((73,), [73]),
]
