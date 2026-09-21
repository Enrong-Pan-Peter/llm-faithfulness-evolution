# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (([], []), []),
    ((['hi', 'admin'], ['hi', 'hi', 'admin', 'project']), ['hi', 'admin']),
    ((['4'], ['1', '2', '3', '4', '5']), ['4']),
    ((['hi', 'admin'], ['hI', 'Hi']), ['hI', 'Hi']),
    ((['hi', 'admin'], ['hI', 'hi', 'hi']), ['hI', 'hi', 'hi']),
    ((['hi', 'admin'], ['hi', 'hi']), ['hi', 'hi']),
    (([], ['this']), []),
]
