# Development tests: (tuple of positional arguments, expected return value).
# This file is parsed as literals, never executed. The model may see these.
TESTS = [
    (('Mudasir Hanif ',), 'Mudasir_Hanif_'),
    (('Yellow Yellow  Dirty  Fellow',), 'Yellow_Yellow__Dirty__Fellow'),
    (('   Exa 1 2 2 mple',), '-Exa_1_2_2_mple'),
]
