# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('headache', 'pentadactyl'), 'eadac'),
    (('thisisatest', 'testing123testing'), 'tsitest'),
    (('TATAGC', 'TAGCAG'), 'TAAG'),
    (('XMJYAUZ', 'MZJAWXU'), 'MJAU'),
    (('ABCD', 'XBCYDQ'), 'BCD'),
]
