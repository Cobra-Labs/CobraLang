# codegen/llvm.py
from parser import *

class LLVMCodegen:
    def __init__(self, tree: Program):
        self.tree     = tree
        self.output   = []
        self.strings  = []   # globale String-Konstanten
        self.tmp      = 0    # temporäre Register (%0, %1, ...)
        self.scope    = {}   # name → llvm register

    def fresh(self) -> str:
        self.tmp += 1
        return f"%t{self.tmp}"

    def emit(self, line: str):
        self.output.append(line)

    def generate(self) -> str:
        # Erst alle Funktionen generieren
        for node in self.tree.body:
            if isinstance(node, FuncDef):
                self.gen_funcdef(node)

        # Strings an den Anfang
        header = []
        for i, s in enumerate(self.strings):
            length = len(s) + 1  # +1 für \0
            header.append(f'@str{i} = private constant [{length} x i8] c"{s}\\00"')

        return "\n".join(header + [""] + self.output)

    def cobra_type_to_llvm(self, t: str) -> str:
        mapping = {
            "i8":  "i8",  "i16": "i16",
            "i32": "i32", "i64": "i64",
            "u8":  "i8",  "u16": "i16",
            "u32": "i32", "u64": "i64",
            "f32": "float", "f64": "double",
            "bool": "i1",
            "void": "void",
            "ptr<u8>": "i8*",
        }
        return mapping.get(t, "i32")

    def gen_funcdef(self, node: FuncDef):
        self.tmp   = 0
        self.scope = {}

        ret  = self.cobra_type_to_llvm(node.return_type)
        params_ir = ", ".join(
            f"{self.cobra_type_to_llvm(t)} %{n}" for n, t in node.params
        )

        self.emit(f"define {ret} @{node.name}({params_ir}) {{")
        self.emit("entry:")

        # Parameter in Scope laden
        for pname, ptype in node.params:
            self.scope[pname] = (f"%{pname}", self.cobra_type_to_llvm(ptype))

        for stmt in node.body:
            self.gen_stmt(stmt)

        self.emit("}")
        self.emit("")

    def gen_stmt(self, node):
        if isinstance(node, LetStmt):
            self.gen_let(node)
        elif isinstance(node, ReturnStmt):
            self.gen_return(node)
        elif isinstance(node, IfStmt):
            self.gen_if(node)
        else:
            self.gen_expr(node)

    def gen_let(self, node: LetStmt):
        reg, _ = self.gen_expr(node.value)
        self.scope[node.name] = (reg, self.cobra_type_to_llvm(node.type))

    def gen_return(self, node: ReturnStmt):
        reg, type = self.gen_expr(node.value)
        self.emit(f"  ret {type} {reg}")

    def gen_if(self, node: IfStmt):
        cond_reg, _ = self.gen_expr(node.condition)
        then_label  = f"then{self.tmp}"
        else_label  = f"else{self.tmp}"
        end_label   = f"end{self.tmp}"
        self.tmp += 1

        self.emit(f"  br i1 {cond_reg}, label %{then_label}, label %{else_label}")
        self.emit(f"{then_label}:")
        for stmt in node.then_body:
            self.gen_stmt(stmt)
        self.emit(f"  br label %{end_label}")

        self.emit(f"{else_label}:")
        if node.else_body:
            for stmt in node.else_body:
                self.gen_stmt(stmt)
        self.emit(f"  br label %{end_label}")

        self.emit(f"{end_label}:")

    def gen_expr(self, node) -> tuple[str, str]:
        if isinstance(node, Number):
            return (str(node.value), "i32")

        if isinstance(node, StringLit):
            i = len(self.strings)
            self.strings.append(node.value)
            length = len(node.value) + 1
            reg = self.fresh()
            self.emit(f"  {reg} = getelementptr [{length} x i8], [{length} x i8]* @str{i}, i32 0, i32 0")
            return (reg, "i8*")

        if isinstance(node, Ident):
            if node.name not in self.scope:
                raise NameError(f"Unbekannte Variable '{node.name}'")
            return self.scope[node.name]

        if isinstance(node, BinOp):
            return self.gen_binop(node)

        if isinstance(node, FuncCall):
            return self.gen_call(node)

        raise NotImplementedError(f"Unbekannter Node: {type(node)}")

    def gen_binop(self, node: BinOp) -> tuple[str, str]:
        left_reg,  left_type  = self.gen_expr(node.left)
        right_reg, right_type = self.gen_expr(node.right)
        reg = self.fresh()

        ops = {
            "+": "add", "-": "sub",
            "*": "mul", "/": "sdiv",
            "==": "icmp eq", "!=": "icmp ne",
            "<":  "icmp slt", ">":  "icmp sgt",
            "<=": "icmp sle", ">=": "icmp sge",
        }

        instr = ops.get(node.op)
        if not instr:
            raise NotImplementedError(f"Unbekannter Operator: {node.op}")

        self.emit(f"  {reg} = {instr} {left_type} {left_reg}, {right_reg}")
        result_type = "i1" if "icmp" in instr else left_type
        return (reg, result_type)

    def gen_call(self, node: FuncCall) -> tuple[str, str]:
        args = [self.gen_expr(a) for a in node.args]
        args_ir = ", ".join(f"{t} {r}" for r, t in args)
        reg = self.fresh()
        self.emit(f"  {reg} = call i32 @{node.name}({args_ir})")
        return (reg, "i32")

from lexer import tokenize
from parser import Parser
from checker import TypeChecker

source = """\
def add(a: i32, b: i32) -> i32:
    let result: i32 = a + b
    return result

def main() -> i32:
    let x: i32 = add(1, 2)
    return x
"""

tokens  = tokenize(source)
tree    = Parser(tokens).parse()
TypeChecker(tree).check()
ir      = LLVMCodegen(tree).generate()
print(ir)
