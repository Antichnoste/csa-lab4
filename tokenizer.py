import re

def tokenize(code: str) -> list:
    """Лексический анализ: разбиение исходного кода LISP на токены (скобки, числа, строки, имена)"""
    lines = code.splitlines()
    no_comments = [re.sub(r";.*$", "", line) for line in lines]
    code_nc = "\n".join(no_comments)

    token_pattern = r""""([^"\\]*(\\.[^"\\]*)*)"|[\(\)]|[^\s\(\)]+"""
    tokens = []
    for match in re.finditer(token_pattern, code_nc):
        if match.group(1) is not None:
            tokens.append('"' + match.group(1) + '"')
        else:
            tokens.append(match.group(0))
    return tokens
