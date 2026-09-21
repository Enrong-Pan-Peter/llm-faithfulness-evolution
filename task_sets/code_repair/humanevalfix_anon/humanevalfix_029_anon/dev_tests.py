# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((['xxx', 'asd', 'xxy', 'john doe', 'xxxAAA', 'xxx'], 'xxx'), ['xxx', 'xxxAAA', 'xxx']),
]
