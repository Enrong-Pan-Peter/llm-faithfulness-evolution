# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (("1:02:03",), 3723),
    (("02:03",), 123),
    (("45",), 45),
    (("0:00:00",), 0),
    (("10:00",), 600),
]
