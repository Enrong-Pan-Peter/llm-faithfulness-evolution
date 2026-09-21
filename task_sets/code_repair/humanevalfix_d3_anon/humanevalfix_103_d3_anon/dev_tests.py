# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    ((1, 5), '0b11'),
    ((7, 5), -1),
    ((7, 13), '0b1010'),
    ((996, 997), '0b1111100100'),
    ((185, 546), '0b101101110'),
    ((350, 902), '0b1001110010'),
    ((5, 5), '0b101'),
]
