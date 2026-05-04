#!/usr/bin/python3
import argparse
import subprocess
import os
import sys
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
    'while', 'for', 'continue', 'break',
    'struct', 'unsafe', 'import', 'print', 'from', 'in',
}

TOKEN_PATTERNS = [
    ("COMMENT",  r"#[^\n]*"),
    ("STRING",   r'"[^"]*"'),
    ("ARROW",    r"->"),
    ("NUMBER",   r"0x[0-9a-fA-F]+|\d+"),
    ("CHAR", r"'\\?.'"),  # matched 'x' und '\n'
    ("IDENT",    r"[a-zA-Z_][a-zA-Z0-9_]*"),
    ("OP",       r"[+\-*/<>=!&|%]+"),
    ("COLON",    r":"),
    ("COMMA",    r","),
    ("LPAREN",   r"\("),
    ("RPAREN",   r"\)"),
    ("LBRACE",   r"\{"),
    ("RBRACE",   r"\}"),
    ("NEWLINE",  r"\n"),
    ("SPACE",    r"[ \t]+"),
    ("DOT",      r"\."),
    ("LBRACKET", r"\["),
    ("RBRACKET", r"\]"),

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

        if kind == "CHAR":
            kind = "NUMBER"
            if value[1] == '\\':
                # Escape sequence
                if value[2] == 'n':
                    value = str(ord('\n'))
                elif value[2] == 't':
                    value = str(ord('\t'))
                elif value[2] == '0':
                    print("null")
                    value = str(0)
                elif value[2] == 'x':
                    print("hex")
                    hex_val = value[3:5]
                    value = str(int(hex_val, 16))
                else:
                    value = str(ord(value[2]))
            else:
                value = str(ord(value[1]))

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

class WhileStmt(Node):
    def __init__(self, condition, body):
        self.condition = condition
        self.body      = body

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

class StructDef(Node):
    def __init__(self, name, fields):
        self.name = name
        self.fields = fields

class StructLit(Node):
    def __init__(self, name, fields):
        self.name = name
        self.fields = fields

class MemberAccess(Node):
    def __init__(self, obj, member):
        self.obj = obj
        self.member = member

class IndexAccess(Node):
    def __init__(self, obj, index):
        self.obj    =   obj
        self.index  =   index

class ImportStmt(Node):
    def __init__(self, module, symbols=None):
        self.module  = module    # "io" / "lexer"
        self.symbols = symbols   # None = ganzes Modul, ["tokenize"] = from import

class ForStmt(Node):
    def __init__(self, var, start, end, body):
        self.var  = var    # "i"
        self.start = start  # 0 (immer bei range)
        self.end  = end    # 10
        self.body = body

class ContinueStmt(Node):
    pass

class BreakStmt(Node):
    pass

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
            raise SyntaxError(
                f"Zeile {tok.line}: Erwartet {type}, bekommen {tok.type} ({tok.value!r}) — vorheriger Token: {self.tokens[self.pos - 1]}")
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

    def parse_struct(self):
        self.eat("KEYWORD", "struct")
        name = self.eat("IDENT").value
        self.eat("COLON")
        fields = []
        self.skip("NEWLINE")
        self.eat("INDENT")
        self.skip("NEWLINE")
        while self.peek().type not in ("DEDENT", "EOF"):
            fname = self.eat("IDENT").value
            self.eat("COLON")
            ftype = self.parse_type()
            fields.append((fname, ftype))
            self.skip("NEWLINE")
        self.eat("DEDENT")
        return StructDef(name, fields)

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
            if tok.value == "while":
                return self.parse_while()
            if tok.value == "print":
                return self.parse_print()
            if tok.value == "struct":
                return self.parse_struct()
            if tok.value == "import":
                return self.parse_import()
            if tok.value == "continue": self.eat("KEYWORD"); return ContinueStmt()
            if tok.value == "break": self.eat("KEYWORD"); return BreakStmt()
            if tok.value == "from":
                self.eat("KEYWORD", "from")
                module = self.eat("IDENT").value
                self.eat("KEYWORD", "import")
                symbols = [self.eat("IDENT").value]
                while self.peek().type == "COMMA":
                    self.eat("COMMA")
                    symbols.append(self.eat("IDENT").value)
                return ImportStmt(module, symbols)
            if tok.value == "for":
                return self.parse_for()

        return self.parse_expr()

    def parse_print(self):
        self.eat("KEYWORD", "print")
        self.eat("LPAREN")
        arg = self.parse_expr()
        self.eat("RPAREN")
        return FuncCall("print", [arg])


    def parse_funcdef(self):
        self.eat("KEYWORD", "def")
        name = self.eat("IDENT").value
        self.eat("LPAREN")

        params = []
        while self.peek().type != "RPAREN":
            pname = self.eat("IDENT").value
            self.eat("COLON")
            ptype = self.parse_type()
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
        # Geändert von self.eat("TYPE") zu:
        type_str = self.parse_type()
        self.eat("OP", "=")
        value = self.parse_expr()
        return LetStmt(name, type_str, value)

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

    def parse_while(self):
        self.eat("KEYWORD", "while")
        condition = self.parse_expr()
        self.eat("COLON")
        body = self.parse_block()
        return WhileStmt(condition, body)

    def parse_type(self) -> str:
        # Eingebauter Typ
        if self.peek().type == "TYPE":
            t = self.eat("TYPE").value
            if self.peek().value == "<":
                self.eat("OP", "<")
                inner = self.parse_type()
                self.eat("OP", ">")
                return f"{t}<{inner}>"
            return t
        # Struct-Typ (IDENT)
        if self.peek().type == "IDENT":
            return self.eat("IDENT").value
        raise SyntaxError(f"Zeile {self.peek().line}: Erwartet Typ, bekommen {self.peek().type}")

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

        # Arithmetik/Vergleiche zuerst (höhere Priorität)
        while self.peek().type == "OP" and self.peek().value != "=":
            op = self.eat("OP").value
            right = self.parse_primary()
            left = BinOp(left, op, right)

        # Zuweisung zuletzt (niedrigste Priorität)
        if self.peek().type == "OP" and self.peek().value == "=":
            self.eat("OP", "=")
            right = self.parse_expr()  # rechts-assoziativ
            return BinOp(left, "=", right)

        return left

    def parse_import(self):
        self.eat("KEYWORD", "import")
        module = self.eat("IDENT").value
        return ImportStmt(module)

    def parse_for(self):
        self.eat("KEYWORD", "for")
        var = self.eat("IDENT").value
        self.eat("KEYWORD", "in")
        self.eat("IDENT")  # "range"
        self.eat("LPAREN")
        end = self.parse_expr()
        self.eat("RPAREN")
        self.eat("COLON")
        body = self.parse_block()
        return ForStmt(var, Number(0), end, body)

    def parse_primary(self):
        tok = self.peek()
        # Klammern: (expr)
        if tok.type == "LPAREN":
            self.eat("LPAREN")
            expr = self.parse_expr()
            self.eat("RPAREN")
            return expr

        if tok.type == "NUMBER":
            self.eat("NUMBER")
            return Number(int(tok.value, 0))

        if tok.type == "STRING":
            self.eat("STRING")
            return StringLit(tok.value[1:-1])

        if tok.type == "IDENT":
            self.eat("IDENT")
            # Struct literal: Token { ... }
            if self.peek().type == "LBRACE":
                self.eat("LBRACE")
                fields = []
                while self.peek().type != "RBRACE":
                    fname = self.eat("IDENT").value
                    self.eat("COLON")
                    fval = self.parse_expr()
                    fields.append((fname, fval))
                    if self.peek().type == "COMMA":
                        self.eat("COMMA")
                self.eat("RBRACE")
                return StructLit(tok.value, fields)
            # Funktionsaufruf
            if self.peek().type == "LPAREN":
                self.eat("LPAREN")
                args = []
                while self.peek().type != "RPAREN":
                    args.append(self.parse_expr())
                    if self.peek().type == "COMMA":
                        self.eat("COMMA")
                self.eat("RPAREN")
                return FuncCall(tok.value, args)
            # Member access: tok.type
            node = Ident(tok.value)

            # Chaining: .member und [index] beliebig oft
            while self.peek().type in ("DOT", "LBRACKET"):
                if self.peek().type == "DOT":
                    self.eat("DOT")
                    member = self.eat("IDENT").value
                    node = MemberAccess(node, member)
                elif self.peek().type == "LBRACKET":
                    self.eat("LBRACKET")
                    index = self.parse_expr()
                    self.eat("RBRACKET")
                    node = IndexAccess(node, index)

            return node
        raise SyntaxError(f"Zeile {tok.line}: Unerwartetes Token {tok.type} ({tok.value!r})")


BUILTINS = {
    "syscall",
    "cast",
    "print",
    "alloc",
    "streq",
    "isinstance",
    "sleep",
}

# typechecker.py

class TypeError(Exception):
    def __init__(self, message, line=0):
        self.message = message
        self.line    = line

    def __str__(self):
        return f"\nCobraTypeError: {self.message} (Zeile {self.line})\n"

class TypeChecker:
    def __init__(self, tree: Program):
        self.tree = tree
        self.scope = {}
        self.funcs = {}
        self.structs = {}

    def check(self):
        for node in self.tree.body:
            if isinstance(node, LetStmt) and isinstance(node.value, Number):
                self.scope[node.name] = node.type

        # Erst Structs registrieren
        for node in self.tree.body:
            if isinstance(node, StructDef):
                self.structs[node.name] = dict(node.fields)

        # Dann Funktionssignaturen
        for node in self.tree.body:
            if isinstance(node, FuncDef):
                self.funcs[node.name] = (node.params, node.return_type)

        # Dann alles prüfen
        for node in self.tree.body:
            self.check_node(node)

        print("Funcs:", list(self.funcs.keys()))

    def check_node(self, node):
        if isinstance(node, FuncDef):
            self.check_funcdef(node)
        elif isinstance(node, LetStmt):
            self.check_let(node)
        elif isinstance(node, ReturnStmt):
            self.check_return(node)
        elif isinstance(node, IfStmt):
            self.check_if(node)
        elif isinstance(node, WhileStmt):
            self.check_while(node)
        elif isinstance(node, ForStmt):
            self.check_for(node)
        elif isinstance(node, StructDef):
            pass  # bereits registriert
        elif isinstance(node, (BreakStmt, ContinueStmt)):
            pass
        else:
            self.infer_type(node)

    def check_funcdef(self, node: FuncDef):
        # Parameter in Scope laden
        for pname, ptype in node.params:
            self.scope[pname] = ptype
        for stmt in node.body:
            self.check_node(stmt)

    def check_while(self, node: WhileStmt):
        self.infer_type(node.condition)
        for stmt in node.body:
            self.check_node(stmt)

    def check_let(self, node: LetStmt):
        value_type = self.infer_type(node.value)
        int_types = {"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"}
        if isinstance(node.value, Number) and node.type in int_types:
            self.scope[node.name] = node.type
            return
        if isinstance(node.value, FuncCall) and node.value.name == "alloc":
            self.scope[node.name] = node.type
            return

        # ptr<Struct> erlauben
        declared = node.type
        if declared.startswith("ptr<"):
            self.scope[node.name] = node.type
            return

        if value_type != declared and declared not in self.structs:
            raise TypeError(
                f"Typ-Mismatch: '{node.name}' ist {declared}, aber Wert ist {value_type}",
                line=0
            )
        self.scope[node.name] = node.type

    def check_return(self, node: ReturnStmt):
        self.infer_type(node.value)  # prüft, ob Wert gültig ist

    def check_if(self, node: IfStmt):
        self.infer_type(node.condition)
        for stmt in node.then_body:
            self.check_node(stmt)
        if node.else_body:
            for stmt in node.else_body:
                self.check_node(stmt)

    def check_for(self, node: ForStmt):
        self.scope[node.var] = "i32"
        self.infer_type(node.end)
        for stmt in node.body:
            self.check_node(stmt)

    def infer_type(self, node) -> str:
        if isinstance(node, Number):
            return "i32"

        if isinstance(node, StructLit):
            if node.name not in self.structs:
                raise TypeError(f"Unbekannter Struct '{node.name}'")
            return node.name

        if isinstance(node, IndexAccess):
            obj_type = self.infer_type(node.obj)
            # ptr<i32>[i] → i32
            if obj_type.startswith("ptr<"):
                return obj_type[4:-1]  # ptr<i32> → i32
            raise TypeError(f"'{obj_type}' ist nicht indexierbar")

        if isinstance(node, MemberAccess):
            obj_type = self.infer_type(node.obj)
            struct_name = obj_type
            if struct_name.startswith("ptr<"):
                struct_name = struct_name[4:-1]
            if struct_name not in self.structs:
                raise TypeError(f"'{obj_type}' ist kein Struct")
            fields = self.structs[struct_name]
            if node.member not in fields:
                raise TypeError(f"Struct '{struct_name}' hat kein Feld '{node.member}'")
            return fields[node.member]

        if isinstance(node, FuncCall):
            if node.name in BUILTINS:
                if node.name == "syscall": return "i64"
                if node.name == "cast":    return "ptr<u8>"  # Platzhalter
                if node.name == "print": return "void"
                if node.name == "alloc": return "ptr<i32>"
                if node.name == "streq": return "bool"
                if node.name == "isinstance": return "bool"
                if node.name == "sleep": return "void"

            if node.name not in self.funcs:
                return "i32"

        if isinstance(node, StringLit):
            return "ptr<u8>"

        if isinstance(node, Ident):
            if node.name not in self.scope:
                raise TypeError(f"Unbekannte Variable '{node.name}'")
            return self.scope[node.name]

        if isinstance(node, BinOp):
            left = self.infer_type(node.left)
            right = self.infer_type(node.right)
            int_types = {"i8", "i16", "i32", "i64", "u8", "u16", "u32", "u64"}
            if node.op == "=":
                return left  # Zuweisung immer OK
            if left != right:
                if left in int_types and right in int_types:
                    return left
                # Pointer-Kompatibilität
                if left.startswith("ptr<") and right.startswith("ptr<"):
                    return left
                raise TypeError(f"Typ-Mismatch in BinOp: {left} {node.op} {right}")
            return left

        if isinstance(node, FuncCall):
            if node.name not in self.funcs:
                raise TypeError(f"Unbekannte Funktion '{node.name}'")
            params, return_type = self.funcs[node.name]
            if len(node.args) != len(params):
                raise TypeError(f"Falsche Anzahl Argumente für '{node.name}'")
            return return_type

        raise TypeError(f"Unbekannter Node-Typ: {type(node)}")

# codegen/llvm.py



class LLVMCodegen:
    def __init__(self, tree: Program):
        self.tree = tree
        self.output = []
        self.strings = []  # globale String-Konstanten
        self.tmp = 0  # temporäre Register
        self.scope = {}  # name → llvm register
        self.structs = {}  # name → [(field, llvm_type), ...]
        self.struct_ids = {}
        self.loop_end_labels = []
        self.loop_cond_labels = []
        self.global_consts = {}
        self.entry_alloca_pos = 0

    def fresh(self) -> str:
        self.tmp += 1
        return f"%t{self.tmp}"

    def emit(self, line: str):
        self.output.append(line)

    def generate(self) -> str:
        # Erst Structs registrieren
        for node in self.tree.body:
            if isinstance(node, StructDef):
                self.gen_structdef(node)

        for node in self.tree.body:
            if isinstance(node, LetStmt) and isinstance(node.value, Number):
                llty = self.cobra_type_to_llvm(node.type)
                self.global_consts[node.name] = (str(node.value.value), llty)

        # Dann Funktionen
        for node in self.tree.body:
            if isinstance(node, FuncDef):
                self.gen_funcdef(node)

        self.emit("""define void @_start() {
entry:
  %ret = call i32 @main()
  %ret64 = sext i32 %ret to i64
  call i64 asm sideeffect "syscall", "={ax},{ax},{di},~{dirflag},~{fpsr},~{flags}"(i64 60, i64 %ret64)
  ret void
}""")

        header = [
            """define void @__cobra_print_int(i32 %n) {
            entry:
              %is_neg = icmp slt i32 %n, 0
              br i1 %is_neg, label %neg, label %pos
            neg:
              %minus = alloca [1 x i8]
              %mp = getelementptr [1 x i8], [1 x i8]* %minus, i32 0, i32 0
              store i8 45, i8* %mp
              call i64 asm sideeffect "syscall", "={ax},{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i64 1, i64 1, i8* %mp, i64 1)
              %pos_n = sub i32 0, %n
              call void @__cobra_print_int(i32 %pos_n)
              br label %end
            pos:
              %gt9 = icmp sgt i32 %n, 9
              br i1 %gt9, label %recurse, label %digit
            recurse:
              %div = sdiv i32 %n, 10
              call void @__cobra_print_int(i32 %div)
              br label %digit
            digit:
              %mod = srem i32 %n, 10
              %ch = add i32 %mod, 48
              %buf = alloca [1 x i8]
              %bp = getelementptr [1 x i8], [1 x i8]* %buf, i32 0, i32 0
              %ch8 = trunc i32 %ch to i8
              store i8 %ch8, i8* %bp
              call i64 asm sideeffect "syscall", "={ax},{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"(i64 1, i64 1, i8* %bp, i64 1)
              br label %end
            end:
              ret void
            }""",
            """define i64 @strlen(i8* %s) {
            entry:
              br label %loop
            loop:
              %i = phi i64 [ 0, %entry ], [ %i1, %loop ]
              %p = getelementptr i8, i8* %s, i64 %i
              %c = load i8, i8* %p
              %done = icmp eq i8 %c, 0
              %i1 = add i64 %i, 1
              br i1 %done, label %end, label %loop
            end:
              ret i64 %i
            }""",
            """define i1 @streq(i8* %a, i8* %b) {
            entry:
              br label %loop
            loop:
              %i = phi i64 [ 0, %entry ], [ %i1, %loop_next ]
              %pa = getelementptr i8, i8* %a, i64 %i
              %pb = getelementptr i8, i8* %b, i64 %i
              %ca = load i8, i8* %pa
              %cb = load i8, i8* %pb
              %eq = icmp eq i8 %ca, %cb
              %nul = icmp eq i8 %ca, 0
              %i1 = add i64 %i, 1
              br i1 %nul, label %done_eq, label %loop_next
            loop_next:
              br i1 %eq, label %loop, label %done_neq
            done_eq:
              ret i1 1
            done_neq:
              ret i1 0
            }"""
        ]

        # Struct Typ-Definitionen in header
        for name, fields in self.structs.items():
            field_types = ", ".join(t for _, t in fields)
            header.append(f"%{name} = type {{ {field_types} }}")

        for i, s in enumerate(self.strings):
            raw_s = s.encode('utf-8').decode('unicode_escape').encode('latin-1')
            fmt_s = "".join(f"\\{b:02x}" for b in raw_s)
            actual_length = len(raw_s) + 1
            header.append(f'@str{i} = private constant [{actual_length} x i8] c"{fmt_s}\\00"')

        return "\n".join(header + [""] + self.output)

    @staticmethod
    def cobra_type_to_llvm(t: str) -> str:
        mapping = {
            "i8": "i8", "i32": "i32", "i64": "i64",
            "u8": "i8", "u32": "i32", "u64": "i64",
            "bool": "i1", "void": "void",
            "ptr<u8>": "i8*", "ptr<i32>": "i32*",
        }
        if t in mapping:
            return mapping[t]
        if t.startswith("ptr<"):
            inner = t[4:-1]  # "Token", "i32", "u8" ...
            inner_ll = mapping.get(inner, f"%{inner}")  # i32→i32, Token→%Token
            return f"{inner_ll}*"  # → "i32*" oder "%Token*"
        return f"%{t}*"  # reiner Struct-Name → "%Token*"

    def gen_funcdef(self, node: FuncDef):
        self.tmp = 0
        self.scope = {}
        ret = self.cobra_type_to_llvm(node.return_type)
        params_ir = ", ".join(f"{self.cobra_type_to_llvm(t)} %{n}" for n, t in node.params)

        self.emit(f"define {ret} @{node.name}({params_ir}) {{")
        self.emit("entry:")

        for pname, ptype in node.params:
            llty = self.cobra_type_to_llvm(ptype)
            ptr = self.fresh()
            self.emit(f"  {ptr} = alloca {llty}")
            self.emit(f"  store {llty} %{pname}, {llty}* {ptr}")
            self.scope[pname] = (ptr, llty, True)

        self.entry_alloca_pos = len(self.output)  # NEU: nach param-allocas

        for stmt in node.body:
            self.gen_stmt(stmt)

        if node.return_type == "void":
            self.emit("  ret void")
        self.emit("}")

    def gen_stmt(self, node):
        if isinstance(node, LetStmt):
            self.gen_let(node)
        elif isinstance(node, ReturnStmt):
            self.gen_return(node)
        elif isinstance(node, WhileStmt):
            self.gen_while(node)
        elif isinstance(node, IfStmt):
            self.gen_if(node)
        elif isinstance(node, ForStmt):
            self.gen_for(node)
        elif isinstance(node, ContinueStmt):
            self.emit(f"  br label %{self.loop_cond_labels[-1]}")
        elif isinstance(node, BreakStmt):
            self.emit(f"  br label %{self.loop_end_labels[-1]}")
        else:
            self.gen_expr(node)

    def gen_let(self, node: LetStmt):
        if isinstance(node.value, FuncCall) and node.value.name == "alloc":
            llty = self.cobra_type_to_llvm(node.type)
            reg, _ = self.gen_alloc(node.value, llty)
            self.scope[node.name] = (reg, llty, False)
            return

        reg, ty = self.gen_expr(node.value)
        if ty.endswith("*"):
            self.scope[node.name] = (reg, ty, False)
            return

        ptr = self.fresh()
        # alloca in entry-Block einfügen statt hier
        self.output.insert(self.entry_alloca_pos, f"  {ptr} = alloca {ty}")
        self.entry_alloca_pos += 1  # weil wir eine Zeile eingefügt haben

        self.emit(f"  store {ty} {reg}, {ty}* {ptr}")
        self.scope[node.name] = (ptr, ty, True)

    def gen_return(self, node: ReturnStmt):
        reg, type = self.gen_expr(node.value)
        self.emit(f"  ret {type} {reg}")

    def gen_expr(self, node) -> tuple[str, str] | None:
        if isinstance(node, Number):
            return str(node.value), "i32"
        if isinstance(node, StringLit):
            i = len(self.strings)
            self.strings.append(node.value)
            length = len(node.value.replace("\\n", "n")) + 1
            reg = self.fresh()
            self.emit(f"  {reg} = getelementptr [{length} x i8], [{length} x i8]* @str{i}, i32 0, i32 0")
            return reg, "i8*"
        if isinstance(node, StructLit):
            return self.gen_structlit(node)

        if isinstance(node, MemberAccess):
            return self.gen_member_access(node)
        if isinstance(node, Ident):
            if node.name in self.global_consts:
                val, ty = self.global_consts[node.name]
                return val, ty
            ptr, ty, is_ptr = self.scope[node.name]
            if is_ptr:
                reg = self.fresh()
                self.emit(f"  {reg} = load {ty}, {ty}* {ptr}")
                return reg, ty
            return ptr, ty
        if isinstance(node, FuncCall):
            return self.gen_call(node)
        if isinstance(node, IndexAccess):
            return self.gen_index_access(node)
        if isinstance(node, IfStmt):
            self.gen_if(node)
        if isinstance(node, BinOp):
            if node.op == "=":
                reg, ty = self.gen_expr(node.right)
                if isinstance(node.left, Ident):
                    ptr, _, _ = self.scope[node.left.name]
                    self.emit(f"  store {ty} {reg}, {ty}* {ptr}")
                if isinstance(node.left, IndexAccess):
                    ptr_reg, _ = self.gen_expr(node.left.obj)
                    idx_reg, _ = self.gen_expr(node.left.index)
                    gep_reg = self.fresh()
                    self.emit(f"  {gep_reg} = getelementptr i32, i32* {ptr_reg}, i32 {idx_reg}")
                    self.emit(f"  store i32 {reg}, i32* {gep_reg}")
                    return reg, ty
                if isinstance(node.left, MemberAccess):
                    # tokens[tok_count].type = val
                    obj = node.left.obj  # IndexAccess(tokens, tok_count)
                    member = node.left.member

                    ptr_reg, ptr_type = self.gen_expr(obj)  # gibt %Token* zurück
                    struct_name = ptr_type.lstrip("%").rstrip("*")
                    fields = self.structs[struct_name]
                    idx = next(i for i, (f, _) in enumerate(fields) if f == member)
                    field_type = fields[idx][1]

                    val_reg, val_ty = self.gen_expr(node.right)
                    gep = self.fresh()
                    self.emit(f"  {gep} = getelementptr %{struct_name}, %{struct_name}* {ptr_reg}, i32 0, i32 {idx}")
                    self.emit(f"  store {field_type} {val_reg}, {field_type}* {gep}")
                    return val_reg, val_ty
                return reg, ty

            l_reg, l_ty = self.gen_expr(node.left)
            r_reg, _ = self.gen_expr(node.right)
            reg = self.fresh()

            ops = {
                "+": "add", "-": "sub", "*": "mul", "/": "sdiv", "%": "srem",
                "==": "icmp eq", "!=": "icmp ne",
                "<": "icmp slt", ">": "icmp sgt",
                "<=": "icmp sle", ">=": "icmp sge",
            }
            instr = ops.get(node.op, "add")
            self.emit(f"  {reg} = {instr} {l_ty} {l_reg}, {r_reg}")
            result_type = "i1" if "icmp" in instr else l_ty
            return reg, result_type
        return None

    def gen_call(self, node: FuncCall) -> tuple[str, str] | None:
        if node.name == "syscall":
            return self.gen_syscall(node)
        if node.name == "print":
            return self.gen_print(node)
        if node.name == "alloc":
            return self.gen_alloc(node)
        if node.name == "streq":
            return self.gen_streq(node)
        if node.name == "isinstance":
            return self.gen_isinstance(node)
        if node.name == "sleep":
            ms_reg, _ = self.gen_expr(node.args[0])
            return self.gen_sleep(ms_reg)

        args = [self.gen_expr(a) for a in node.args]
        args_ir = ", ".join(f"{t} {r}" for r, t in args)
        reg = self.fresh()
        self.emit(f"  {reg} = call i32 @{node.name}({args_ir})")
        return reg, "i32"

    def gen_print(self, node: FuncCall):
        reg, ty = self.gen_expr(node.args[0])

        if ty == "i8*":
            len_reg = self.fresh()
            self.emit(f"  {len_reg} = call i64 @strlen(i8* {reg})")
            syscall_reg = self.fresh()
            constraints = "={ax},{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"
            self.emit(
                f'  {syscall_reg} = call i64 asm sideeffect "syscall", "{constraints}"(i64 1, i64 1, i8* {reg}, i64 {len_reg})')
            return syscall_reg, "void"

        if ty == "i32":
            self.emit(f"  call void @__cobra_print_int(i32 {reg})")
            return "%0", "void"

        raise NotImplementedError(f"print() für Typ {ty} noch nicht implementiert")

    def gen_syscall(self, node: FuncCall) -> tuple[str, str]:
        processed = []
        for a in node.args:
            r, t = self.gen_expr(a)
            if t == "i32":  # Syscalls brauchen i64
                nr = self.fresh()
                self.emit(f"  {nr} = sext i32 {r} to i64")
                processed.append((nr, "i64"))
            else:
                processed.append((r, t))

        vals = ", ".join(f"{t} {r}" for r, t in processed)
        constraints = "={ax},{ax},{di},{si},{dx},~{dirflag},~{fpsr},~{flags}"
        reg = self.fresh()
        self.emit(f'  {reg} = call i64 asm sideeffect "syscall", "{constraints}"({vals})')
        return reg, "i64"

    def gen_sleep(self, ms_value_reg):
        struct_ptr = self.fresh()
        self.emit(f"  {struct_ptr} = alloca [2 x i64]")

        sec = self.fresh()
        self.emit(f"  {sec} = udiv i64 {ms_value_reg}, 1000")  # ms zu s

        rem_ms = self.fresh()
        self.emit(f"  {rem_ms} = urem i64 {ms_value_reg}, 1000")  # Restliche ms

        nsec = self.fresh()
        self.emit(f"  {nsec} = mul i64 {rem_ms}, 1000000")  # ms zu ns
        p1 = self.fresh()
        self.emit(f"  {p1} = getelementptr [2 x i64], [2 x i64]* {struct_ptr}, i32 0, i32 0")
        self.emit(f"  store i64 {sec}, i64* {p1}")

        p2 = self.fresh()
        self.emit(f"  {p2} = getelementptr [2 x i64], [2 x i64]* {struct_ptr}, i32 0, i32 1")
        self.emit(f"  store i64 {nsec}, i64* {p2}")
        ptr_int = self.fresh()
        self.emit(f"  {ptr_int} = ptrtoint [2 x i64]* {struct_ptr} to i64")


        res = self.fresh()
        constraints = "={ax},{ax},{di},{si},~{rcx},~{r11},~{flags}"
        self.emit(f'  {res} = call i64 asm sideeffect "syscall", "{constraints}"(i64 35, i64 {ptr_int}, i64 0)')
        return "0", "void"

    def gen_structdef(self, node: StructDef):
        type_id = len(self.structs) + 1
        self.struct_ids[node.name] = type_id
        # _type_id als erstes Feld einfügen
        fields = [("_type_id", "i32")] + [(fname, self.cobra_type_to_llvm(ftype)) for fname, ftype in node.fields]
        self.structs[node.name] = fields

    def gen_structlit(self, node: StructLit) -> tuple[str, str]:
        reg = self.fresh()
        self.emit(f"  {reg} = alloca %{node.name}")

        # _type_id automatisch als erstes Feld setzen
        type_id = self.struct_ids[node.name]
        id_ptr = self.fresh()
        self.emit(f"  {id_ptr} = getelementptr %{node.name}, %{node.name}* {reg}, i32 0, i32 0")
        self.emit(f"  store i32 {type_id}, i32* {id_ptr}")

        # Rest der Felder — Index startet bei 1 wegen _type_id
        for i, (fname, fval) in enumerate(node.fields):
            val_reg, val_type = self.gen_expr(fval)
            ptr_reg = self.fresh()
            self.emit(f"  {ptr_reg} = getelementptr %{node.name}, %{node.name}* {reg}, i32 0, i32 {i + 1}")
            self.emit(f"  store {val_type} {val_reg}, {val_type}* {ptr_reg}")

        return reg, f"%{node.name}*"

    def gen_member_access(self, node: MemberAccess) -> tuple[str, str]:
        obj_reg, obj_type = self.gen_expr(node.obj)

        struct_name = obj_type.lstrip("%").rstrip("*")

        if struct_name not in self.structs:
            raise ValueError(f"Unbekannter Struct '{struct_name}' (typ: {obj_type})")

        fields = self.structs[struct_name]
        idx = next(i for i, (f, _) in enumerate(fields) if f == node.member)
        field_type = fields[idx][1]
        ptr_reg = self.fresh()
        val_reg = self.fresh()

        struct_ptr_type = obj_type if obj_type.endswith("*") else f"{obj_type}*"
        base_type = struct_ptr_type[:-1]  # "%Token"

        self.emit(f"  {ptr_reg} = getelementptr {base_type}, {base_type}* {obj_reg}, i32 0, i32 {idx}")
        self.emit(f"  {val_reg} = load {field_type}, {field_type}* {ptr_reg}")
        return val_reg, field_type

    def gen_while(self, node: WhileStmt):
        loop_label = f"while_cond{self.tmp}"
        body_label = f"while_body{self.tmp}"
        end_label  = f"while_end{self.tmp}"
        self.loop_end_labels.append(end_label)
        self.loop_cond_labels.append(loop_label)
        self.tmp += 1

        # Sprung in die Bedingung
        self.emit(f"  br label %{loop_label}")

        # Bedingung prüfen
        self.emit(f"{loop_label}:")
        cond_reg, cond_type = self.gen_expr(node.condition)

        # Falls Bedingung i32 ist → zu i1 konvertieren
        if cond_type == "i32":
            cmp_reg = self.fresh()
            self.emit(f"  {cmp_reg} = icmp ne i32 {cond_reg}, 0")
            cond_reg = cmp_reg

        self.emit(f"  br i1 {cond_reg}, label %{body_label}, label %{end_label}")

        # Body
        self.emit(f"{body_label}:")
        for stmt in node.body:
            self.gen_stmt(stmt)
        self.emit(f"  br label %{loop_label}")

        # Ende
        self.emit(f"{end_label}:")
        self.loop_end_labels.pop()
        self.loop_cond_labels.pop()

    def gen_if(self, node: IfStmt):
        then_label = f"if_then{self.tmp}"
        else_label = f"if_else{self.tmp}"
        end_label = f"if_end{self.tmp}"
        self.tmp += 1

        cond_reg, cond_type = self.gen_expr(node.condition)

        # i32 → i1 konvertieren
        if cond_type == "i32":
            cmp_reg = self.fresh()
            self.emit(f"  {cmp_reg} = icmp ne i32 {cond_reg}, 0")
            cond_reg = cmp_reg

        if node.else_body:
            self.emit(f"  br i1 {cond_reg}, label %{then_label}, label %{else_label}")
        else:
            self.emit(f"  br i1 {cond_reg}, label %{then_label}, label %{end_label}")

        # Then
        self.emit(f"{then_label}:")
        for stmt in node.then_body:
            self.gen_stmt(stmt)
        self.emit(f"  br label %{end_label}")

        # Else
        if node.else_body:
            self.emit(f"{else_label}:")
            for stmt in node.else_body:
                self.gen_stmt(stmt)
            self.emit(f"  br label %{end_label}")

        self.emit(f"{end_label}:")

    def gen_alloc(self, node: FuncCall, target_type: str = "i32*") -> tuple[str, str]:
        count_reg, _ = self.gen_expr(node.args[0])

        # Elementgröße bestimmen
        elem_type = target_type.rstrip("*")  # "%Token" oder "i32"
        # Größe: für Structs nehmen wir 64 Bytes als konservative Schätzung
        # Für i32 = 4 Bytes
        if elem_type == "i32":
            size_mul = 4
            self.emit(f"  %_sz{self.tmp} = mul i32 {count_reg}, {size_mul}")
        else:
            # Struct: mit getelementptr Trick die Größe berechnen
            size_reg = self.fresh()
            self.emit(f"  {size_reg} = getelementptr {elem_type}, {elem_type}* null, i32 1")
            sz_int = self.fresh()
            self.emit(f"  {sz_int} = ptrtoint {elem_type}* {size_reg} to i64")
            mul_reg = self.fresh()
            count64 = self.fresh()
            self.emit(f"  {count64} = sext i32 {count_reg} to i64")
            self.emit(f"  {mul_reg} = mul i64 {sz_int}, {count64}")
            ptr_raw = self.fresh()
            constraints = "={ax},{ax},{di},{si},{dx},{r10},{r8},{r9},~{dirflag},~{fpsr},~{flags}"
            self.emit(
                f'  {ptr_raw} = call i64 asm sideeffect "syscall", "{constraints}"(i64 9, i64 0, i64 {mul_reg}, i64 3, i64 34, i64 -1, i64 0)')
            cast_reg = self.fresh()
            self.emit(f"  {cast_reg} = inttoptr i64 {ptr_raw} to {target_type}")
            return cast_reg, target_type

        # i32-Pfad (wie bisher)
        size_reg = f"%_sz{self.tmp}"
        size64 = self.fresh()
        self.emit(f"  {size64} = sext i32 {size_reg} to i64")
        ptr_raw = self.fresh()
        constraints = "={ax},{ax},{di},{si},{dx},{r10},{r8},{r9},~{dirflag},~{fpsr},~{flags}"
        self.emit(
            f'  {ptr_raw} = call i64 asm sideeffect "syscall", "{constraints}"(i64 9, i64 0, i64 {size64}, i64 3, i64 34, i64 -1, i64 0)')
        cast_reg = self.fresh()
        self.emit(f"  {cast_reg} = inttoptr i64 {ptr_raw} to i32*")
        return cast_reg, "i32*"

    def gen_index_access(self, node: IndexAccess) -> tuple[str, str]:
        ptr_reg, ptr_type = self.gen_expr(node.obj)
        idx_reg, _ = self.gen_expr(node.index)

        if ptr_type.endswith("*"):
            elem_type = ptr_type[:-1]
        else:
            elem_type = "i32"

        gep_reg = self.fresh()
        self.emit(f"  {gep_reg} = getelementptr {elem_type}, {elem_type}* {ptr_reg}, i32 {idx_reg}")

        if elem_type.startswith("%"):
            return gep_reg, f"{elem_type}*"

        val_reg = self.fresh()
        self.emit(f"  {val_reg} = load {elem_type}, {elem_type}* {gep_reg}")
        return val_reg, elem_type

    def gen_streq(self, node: FuncCall) -> tuple[str, str]:
        a_reg, _ = self.gen_expr(node.args[0])
        b_reg, _ = self.gen_expr(node.args[1])
        reg = self.fresh()
        self.emit(f"  {reg} = call i1 @streq(i8* {a_reg}, i8* {b_reg})")
        return reg, "i1"

    def gen_isinstance(self, node: FuncCall) -> tuple[str, str]:
        # isinstance(obj, TypeName)
        obj_reg, obj_type = self.gen_expr(node.args[0])
        type_name = node.args[1].name  # Ident Node
        type_id = self.struct_ids[type_name]

        # _type_id lesen (Index 0)
        struct_name = obj_type.lstrip("%").rstrip("*")
        id_ptr = self.fresh()
        id_val = self.fresh()
        self.emit(f"  {id_ptr} = getelementptr %{struct_name}, %{struct_name}* {obj_reg}, i32 0, i32 0")
        self.emit(f"  {id_val} = load i32, i32* {id_ptr}")

        # Vergleichen
        cmp_reg = self.fresh()
        self.emit(f"  {cmp_reg} = icmp eq i32 {id_val}, {type_id}")
        return cmp_reg, "i1"

    def gen_for(self, node: ForStmt):
        # Variable allozieren
        ptr = self.fresh()
        self.emit(f"  {ptr} = alloca i32")
        self.emit(f"  store i32 0, i32* {ptr}")
        self.scope[node.var] = (ptr, "i32", True)

        loop_label = f"for_cond{self.tmp}"
        body_label = f"for_body{self.tmp}"
        end_label = f"for_end{self.tmp}"
        self.tmp += 1

        self.emit(f"  br label %{loop_label}")
        self.emit(f"{loop_label}:")

        # Bedingung: i < end
        cur_reg = self.fresh()
        self.emit(f"  {cur_reg} = load i32, i32* {ptr}")
        end_reg, _ = self.gen_expr(node.end)
        cmp_reg = self.fresh()
        self.emit(f"  {cmp_reg} = icmp slt i32 {cur_reg}, {end_reg}")
        self.emit(f"  br i1 {cmp_reg}, label %{body_label}, label %{end_label}")

        # Body
        self.emit(f"{body_label}:")
        for stmt in node.body:
            self.gen_stmt(stmt)

        # i = i + 1
        inc_reg = self.fresh()
        cur2 = self.fresh()
        self.emit(f"  {cur2} = load i32, i32* {ptr}")
        self.emit(f"  {inc_reg} = add i32 {cur2}, 1")
        self.emit(f"  store i32 {inc_reg}, i32* {ptr}")
        self.emit(f"  br label %{loop_label}")

        self.emit(f"{end_label}:")
def resolve_imports(tree, source_dir, visited=None):
    if visited is None:
        visited = set()

    new_body = []
    for node in tree.body:
        if isinstance(node, ImportStmt):
            module_file = os.path.join(source_dir, f"{node.module}.co")
            if not os.path.exists(module_file):
                raise FileNotFoundError(f"Modul '{node.module}' nicht gefunden: {module_file}")

            # Bei symbol-imports (from x import y) immer laden
            # Bei wildcard-imports (import x) visited prüfen
            if not node.symbols and module_file in visited:
                continue

            if not node.symbols:
                visited.add(module_file)

            with open(module_file, "r") as f:
                mod_source = f.read()
            mod_tokens = tokenize(mod_source)
            mod_tree = Parser(mod_tokens).parse()
            mod_tree = resolve_imports(mod_tree, source_dir, visited)

            if node.symbols:
                for n in mod_tree.body:
                    if isinstance(n, LetStmt) and isinstance(n.value, Number):
                        if n.name not in [x.name for x in new_body if isinstance(x, LetStmt)]:
                            new_body.append(n)
                    if isinstance(n, (StructDef, FuncDef)):
                        existing_names = [x.name for x in new_body if isinstance(x, (StructDef, FuncDef))]
                        if n.name not in existing_names and n.name != "main":
                            new_body.append(n)
            else:
                new_body.extend(mod_tree.body)
        else:
            new_body.append(node)
    return Program(new_body)


def main():
    arg_parser = argparse.ArgumentParser(description="CobraLang Compiler")
    arg_parser.add_argument("input", help="Eingabedatei (.co)")
    arg_parser.add_argument("-o", "--output", default="a.out")
    arg_parser.add_argument("-s", "--asm", action="store_true")
    arg_parser.add_argument("-x", "--hex", action="store_true")
    arg_parser.add_argument("-v", "--verbose", action="store_true")
    args = arg_parser.parse_args()

    def log(msg):
        if args.verbose:
            print(msg)

    if not os.path.exists(args.input):
        print(f"Fehler: Datei '{args.input}' nicht gefunden.")
        sys.exit(1)

    with open(args.input, "r") as f:
        source = f.read()

    print(f"[*] Kompiliere {args.input}...")

    try:
        tokens = tokenize(source)
        log("\n=== TOKENS ===")
        for tok in tokens:
            log(f"  {tok}")

        tree = Parser(tokens).parse()
        log("\n=== AST ===")
        for node in tree.body:
            log(f"  {node}")

        tree = resolve_imports(tree, os.path.dirname(os.path.abspath(args.input)))

        TypeChecker(tree).check()
        log("\n=== TYPCHECK OK ===")

        ir = LLVMCodegen(tree).generate()
        log("\n=== LLVM IR ===")
        log(ir)


    except Exception as e:
        if args.verbose:
            import traceback
            traceback.print_exc()
        print(f"[!] Compiler Fehler: {e}")
        sys.exit(1)

    base_name = args.input.rsplit(".", 1)[0]
    ll_file  = f"{base_name}.ll"
    obj_file = f"{base_name}.o"
    asm_file = f"{base_name}.s"

    with open(ll_file, "w") as f:
        f.write(ir)

    try:
        log("\n=== TOOLCHAIN ===")
        subprocess.run(["llc", "-filetype=obj", "-relocation-model=static", ll_file, "-o", obj_file], check=True)
        log(f"[+] Object File: {obj_file}")

        if args.asm:
            subprocess.run(["llc", "-filetype=asm", "-relocation-model=static", ll_file, "-o", asm_file], check=True)
            print(f"[+] Assembly gespeichert in {asm_file}")

        subprocess.run(["ld", "-static", obj_file, "-o", args.output], check=True)
        print(f"[+] Binary erzeugt: {args.output}")

        if args.hex:
            print(f"[*] Hexdump von {args.output}:")
            subprocess.run(["hexdump", "-C", args.output])

    except subprocess.CalledProcessError as e:
        print(f"[!] Toolchain Fehler: {e}")
    finally:
        # if os.path.exists(ll_file): os.remove(ll_file)
        if os.path.exists(obj_file): os.remove(obj_file)


if __name__ == "__main__":
    main()