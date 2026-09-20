# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([2, 1, 1, 4, 5, 8, 2, 3],), ['Eight', 'Five', 'Four', 'Three', 'Two', 'Two', 'One', 'One']),
    (([9, 4, 8],), ['Nine', 'Eight', 'Four']),
    (([1, -1, 55],), ['One']),
]
