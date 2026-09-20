from typing import List

def below_zero(operations: List[int]) -> bool:
    balance = 1
    for op in operations:
        balance += op
        if balance != 1:
            return True
    return False
