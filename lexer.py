import re

DATATYPES = {
    'i8', 'i16', 'i32', 'i64',
    'u8', 'u16', 'u32', 'u64',
    'f32', 'f64',
    'bool', 'void', 'ptr'
}

KEYWORDS = {
    'def', 'let', 'return',
    'if', 'else', 'elif',
    'while', 'for',
    'struct', 'unsafe', 'import'
}

TOKEN_PATTERNS = [
    ("COMMENT",  r"#[^\n]*"),
    ("STRING",   r'"[^"]*"'),
    ("ARROW",    r"->"),
    ("NUMBER",   r"0x[0-9a-fA-F]+|\d+"),
    ("IDENT",    r"[a-zA-Z_][a-zA-Z0-9_]*"),
    ("OP",       r"[+\-*/<>=!&|]+"),
    ("COLON",    r":"),
    ("COMMA",    r","),
    ("LPAREN",   r"\("),
    ("RPAREN",   r"\)"),
    ("LBRACE",   r"\{"),
    ("RBRACE",   r"\}"),
    ("NEWLINE",  r"\n"),
    ("SPACE",    r"[ \t]+"),
]

MASTER = "|".join(f"(?P<{n}>{p})" for n, p in TOKEN_PATTERNS)

class CobraError(Exception):
    def __init__(self, message, source, line, col, file="<stdin>"):
        self.message = message
        self.source  = source
        self.line    = line
        self.col     = col
        self.file    = file

    def __str__(self):
        lines   = self.source.splitlines()
        src_line = lines[self.line - 1] if self.line <= len(lines) else ""
        prefix  = f"  Zeile {self.line} | "
        padding = " " * len(prefix)

        return (
            f"\nCobraError: {self.message} in {self.file}\n\n"
            f"{prefix}{src_line}\n"
            f"{padding}{' ' * self.col}^\n"
        )

class Token:
    def __init__(self, type, value, line):
        self.type  = type
        self.value = value
        self.line  = line

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, line={self.line})"

def tokenize(source: str) -> list[Token]:
    tokens = []
    indent_stack = [0]
    line_num = 1
    line_start = 0
    at_line_start = True

    for m in re.finditer(MASTER, source):
        kind = m.lastgroup
        value = m.group()
        col = m.start() - line_start

        # 1. Unwichtiges überspringen
        if kind in ("COMMENT", "SPACE"):
            continue

        # 2. Zeilenende
        if kind == "NEWLINE":
            if not at_line_start:
                tokens.append(Token("NEWLINE", "\\n", line_num))
            line_num += 1
            line_start = m.end()
            at_line_start = True
            continue

        # 3. INDENT / DEDENT am Zeilenanfang
        if at_line_start:
            at_line_start = False
            indent = col

            if indent > indent_stack[-1]:
                indent_stack.append(indent)
                tokens.append(Token("INDENT", indent, line_num))
            elif indent < indent_stack[-1]:
                while indent_stack[-1] > indent:
                    indent_stack.pop()
                    tokens.append(Token("DEDENT", indent, line_num))

        # 4. IDENT -> vielleicht KEYWORD oder TYPE?
        if kind == "IDENT":
            if value in KEYWORDS:
                kind = "KEYWORD"
            elif value in DATATYPES:
                kind = "TYPE"

        tokens.append(Token(kind, value, line_num))

    # nach der for-Schleife, vor dem EOF
    unmatched = re.sub(MASTER, "", source)
    if unmatched.strip():
        raise CobraError(f"Unbekanntes Zeichen {unmatched[0]!r}", source, 1, 0)

    # 5. Dateiende — alle offenen Blöcke schließen
    while len(indent_stack) > 1:
        indent_stack.pop()
        tokens.append(Token("DEDENT", 0, line_num))

    tokens.append(Token("EOF", "", line_num))
    return tokens
