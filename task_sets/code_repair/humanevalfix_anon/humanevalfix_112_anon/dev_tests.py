# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('abcde', 'ae'), ['bcd', False]),
    (('abcdedcba', 'ab'), ['cdedc', True]),
    (('a', 'a'), ['', True]),
    (('abcdedcba', 'v'), ['abcdedcba', True]),
    (('mamma', 'mia'), ['', True]),
]
