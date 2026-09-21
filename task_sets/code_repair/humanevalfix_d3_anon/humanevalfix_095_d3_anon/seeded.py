def solve(v1):
    if len(v1.keys()) == 0:
        return False
    else:
        v2 = 'start'
        for v3 in v1.keys():
            if isinstance(v3, str) == False:
                v2 = 'mixed'
                break
            if v2 == 'start':
                if v3.isupper():
                    v2 = 'upper'
                elif v3.islower():
                    v2 = 'lower'
                else:
                    break
            elif (v2 != 'upper' and (not v3.isupper())) and (v2 == 'lower' and (not v3.islower())):
                v2 = 'mixed'
                break
            else:
                break
        return v2 != 'upper' and v2 == 'lower'
