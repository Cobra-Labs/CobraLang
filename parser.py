# parser.py

# --- AST Nodes ---

class Node:
    def __repr__(self):
        fields = ", ".join(f"{k}={v!r}" for k, v in vars(self).items())
        return f"{self.__class__.__name__}({fields})"

class Program(Node):
    def __init__(self, body: list):
        self.body = body

class FuncDef(Node):
    def __init__(self, name, params, return_type, body):
        self.name        = name
        self.params      = params       # [(name, type), ...]
        self.return_type = return_type
        self.body        = body

class LetStmt(Node):
    def __init__(self, name, type, value):
        self.name  = name
        self.type  = type
        self.value = value

class ReturnStmt(Node):
    def __init__(self, value):
        self.value = value

class IfStmt(Node):
    def __init__(self, condition, then_body, else_body=None):
        self.condition = condition
        self.then_body = then_body
        self.else_body = else_body

class BinOp(Node):
    def __init__(self, left, op, right):
        self.left  = left
        self.op    = op
        self.right = right

class Ident(Node):
    def __init__(self, name):
        self.name = name

class Number(Node):
    def __init__(self, value):
        self.value = value

class StringLit(Node):
    def __init__(self, value):
        self.value = value

class FuncCall(Node):
    def __init__(self, name, args):
        self.name = name
        self.args = args

# --- Parser ---

class Parser:
    def __init__(self, tokens: list):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos]

    def eat(self, type=None, value=None):
        tok = self.tokens[self.pos]
        if type and tok.type != type:
            raise SyntaxError(f"Zeile {tok.line}: Erwartet {type}, bekommen {tok.type} ({tok.value!r})")
        if value and tok.value != value:
            raise SyntaxError(f"Zeile {tok.line}: Erwartet {value!r}, bekommen {tok.value!r}")
        self.pos += 1
        return tok

    def skip(self, *types):
        while self.peek().type in types:
            self.pos += 1

    def parse(self) -> Program:
        body = []
        self.skip("NEWLINE")
        while self.peek().type != "EOF":
            body.append(self.parse_statement())
            self.skip("NEWLINE")
        return Program(body)

    def parse_statement(self):
        tok = self.peek()

        if tok.type == "KEYWORD":
            if tok.value == "def":
                return self.parse_funcdef()
            if tok.value == "let":
                return self.parse_let()
            if tok.value == "return":
                return self.parse_return()
            if tok.value == "if":
                return self.parse_if()

        return self.parse_expr()

    def parse_funcdef(self):
        self.eat("KEYWORD", "def")
        name = self.eat("IDENT").value
        self.eat("LPAREN")

        params = []
        while self.peek().type != "RPAREN":
            pname = self.eat("IDENT").value
            self.eat("COLON")
            ptype = self.eat("TYPE").value
            params.append((pname, ptype))
            if self.peek().type == "COMMA":
                self.eat("COMMA")

        self.eat("RPAREN")

        return_type = "void"
        if self.peek().type == "ARROW":
            self.eat("ARROW")
            return_type = self.eat("TYPE").value

        self.eat("COLON")
        body = self.parse_block()
        return FuncDef(name, params, return_type, body)

    def parse_let(self):
        self.eat("KEYWORD", "let")
        name = self.eat("IDENT").value
        self.eat("COLON")
        type = self.eat("TYPE").value
        self.eat("OP", "=")
        value = self.parse_expr()
        return LetStmt(name, type, value)

    def parse_return(self):
        self.eat("KEYWORD", "return")
        value = self.parse_expr()
        return ReturnStmt(value)

    def parse_if(self):
        self.eat("KEYWORD", "if")
        condition = self.parse_expr()
        self.eat("COLON")
        then_body = self.parse_block()

        else_body = None
        if self.peek().type == "KEYWORD" and self.peek().value == "else":
            self.eat("KEYWORD", "else")
            self.eat("COLON")
            else_body = self.parse_block()

        return IfStmt(condition, then_body, else_body)

    def parse_block(self):
        stmts = []
        self.skip("NEWLINE")
        self.eat("INDENT")
        self.skip("NEWLINE")
        while self.peek().type not in ("DEDENT", "EOF"):
            stmts.append(self.parse_statement())
            self.skip("NEWLINE")
        self.eat("DEDENT")
        return stmts

    def parse_expr(self):
        left = self.parse_primary()

        while self.peek().type == "OP":
            op = self.eat("OP").value
            right = self.parse_primary()
            left = BinOp(left, op, right)

        return left

    def parse_primary(self):
        tok = self.peek()

        if tok.type == "NUMBER":
            self.eat("NUMBER")
            return Number(int(tok.value, 0))

        if tok.type == "STRING":
            self.eat("STRING")
            return StringLit(tok.value[1:-1])

        if tok.type == "IDENT":
            self.eat("IDENT")
            if self.peek().type == "LPAREN":
                self.eat("LPAREN")
                args = []
                while self.peek().type != "RPAREN":
                    args.append(self.parse_expr())
                    if self.peek().type == "COMMA":
                        self.eat("COMMA")
                self.eat("RPAREN")
                return FuncCall(tok.value, args)
            return Ident(tok.value)

        raise SyntaxError(f"Zeile {tok.line}: Unerwartetes Token {tok.type} ({tok.value!r})")
