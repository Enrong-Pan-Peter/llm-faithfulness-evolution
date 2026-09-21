# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('s1sdf3.asd',), 'No'),
    (('this_is_valid.txtexe',), 'No'),
    (('1example.dll',), 'No'),
    (('MY16FILE3.exe',), 'Yes'),
    (('_Y.txt',), 'No'),
    (('/this_is_valid.dll',), 'No'),
    (('#this2_i4s_5valid.ten',), 'No'),
    (('this_is_12valid.6exe4.txt',), 'No'),
    (('I563_No.exe',), 'Yes'),
    (('no_one#knows.dll',), 'Yes'),
    (('I563_Yes3.txtt',), 'No'),
    (('final132',), 'No'),
    (('.txt',), 'No'),
]
