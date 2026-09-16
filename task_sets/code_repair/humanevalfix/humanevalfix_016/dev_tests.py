# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('abcdecadeCADE',), 5),
    (('Jerry jERRY JeRRRY',), 5),
    (('abcde',), 5),
]
