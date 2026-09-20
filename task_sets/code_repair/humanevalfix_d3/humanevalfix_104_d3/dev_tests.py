# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([15, 33, 1422, 1],), [1, 15, 33]),
    (([152, 323, 1422, 10],), []),
    (([12345, 2033, 111, 151],), [111, 151]),
]
