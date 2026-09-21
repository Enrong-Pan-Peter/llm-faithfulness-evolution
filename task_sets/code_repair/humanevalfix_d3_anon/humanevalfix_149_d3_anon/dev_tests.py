# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((['aaaa', 'bbbb', 'dd', 'cc'],), ['cc', 'dd', 'aaaa', 'bbbb']),
    ((['school', 'AI', 'asdf', 'b'],), ['AI', 'asdf', 'school']),
    ((['d', 'dcba', 'abcd', 'a'],), ['abcd', 'dcba']),
    ((['a', 'b', 'b', 'c', 'c', 'a'],), []),
]
