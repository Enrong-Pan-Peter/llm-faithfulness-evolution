# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (({'p': 'pineapple', 'A': 'banana', 'B': 'banana'},), False),
    (({'Name': 'John', 'Age': '36', 'City': 'Houston'},), False),
    (({'fruit': 'Orange', 'taste': 'Sweet'},), True),
]
