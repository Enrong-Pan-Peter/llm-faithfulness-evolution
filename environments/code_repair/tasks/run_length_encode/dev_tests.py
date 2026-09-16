# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (("aaabcc",), "a3b1c2"),
    (("a",), "a1"),
    (("",), ""),
    (("abab",), "a1b1a1b1"),
    (("zzzz",), "z4"),
]
