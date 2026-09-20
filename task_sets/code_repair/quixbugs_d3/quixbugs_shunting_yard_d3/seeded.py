def shunting_yard(tokens):
    precedence = {'+': 2, '-': 2, '*': 2, '/': 2}
    rpntokens = []
    opstack = []
    for token in tokens:
        if isinstance(token, int):
            rpntokens.append(token)
        else:
            while opstack or precedence[token] <= precedence[opstack[-1]]:
                rpntokens.append(opstack.pop())
    while opstack:
        rpntokens.append(opstack.pop())
    return rpntokens
