import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from isa import AddressingMode, Instruction, Opcode, write_binary

GLOBAL_BASE = 0x1000

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

class LispParser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def parse(self):
        if self.tokens[self.pos] == "(":
            self.pos += 1
            lst = []
            while self.tokens[self.pos] != ")":
                lst.append(self.parse())
            self.pos += 1
            return lst
        return self.atom(self.tokens[self.pos])

    def atom(self, token):
        self.pos += 1
        if token.startswith('"') and token.endswith('"'):
            return {"type": "string", "value": token[1:-1].replace("\\n", "\n").replace("\\t", "\t")}
        try:
            return int(token)
        except ValueError:
            return token

    def parse_program(self):
        program = []
        while self.pos < len(self.tokens):
            program.append(self.parse())
        return program

def ast_to_expr(ast):
    if isinstance(ast, int):
        return {"type": "number", "value": ast}
    if isinstance(ast, dict) and ast.get("type") == "string":
        return ast
    if isinstance(ast, str):
        return {"type": "var", "name": ast}

    head, *args = ast

    dispatch = {
        "defvar": _parse_defvar,
        "setq": _parse_setq,
        "defun": _parse_defun,
        "if": _parse_if,
        "loop": _parse_loop,
        "return": _parse_return,
        "print": _parse_print,
        "in": _parse_in,
        "out": _parse_out
    }

    if head in ("+", "-", "*", "/", "mod", "=", "!=", "<", ">"):
        return _parse_binop(head, args)

    handler = dispatch.get(head)
    if handler:
        return handler(args)

    return _parse_call(head, args)

def _parse_defvar(args):
    expr = ast_to_expr(args[1]) if len(args) > 1 else None
    return {"type": "defvar", "name": args[0], "expr": expr}

def _parse_setq(args):
    return {"type": "setq", "name": args[0], "expr": ast_to_expr(args[1])}

def _parse_defun(args):
    return {"type": "defun", "name": args[0], "params": args[1], "body": [ast_to_expr(b) for b in args[2:]]}

def _parse_binop(op, args):
    left, right = args
    return {"type": "binop", "op": op, "left": ast_to_expr(left), "right": ast_to_expr(right)}

def _parse_if(args):
    return {
        "type": "if",
        "cond": ast_to_expr(args[0]),
        "then": ast_to_expr(args[1]),
        "else": ast_to_expr(args[2]) if len(args) > 2 else None,
    }

def _parse_loop(args):
    return {"type": "loop", "body": [ast_to_expr(stmt) for stmt in args]}

def _parse_return(args):
    return {"type": "return", "expr": ast_to_expr(args[0])}

def _parse_print(args):
    return {"type": "print", "value": ast_to_expr(args[0])}

def _parse_in(args):
    return {"type": "in", "port": ast_to_expr(args[0])}

def _parse_out(args):
    return {"type": "out", "port": ast_to_expr(args[0]), "value": ast_to_expr(args[1])}

def _parse_call(name, args):
    return {"type": "call", "name": name, "args": [ast_to_expr(a) for a in args]}

def parse(tokens: list) -> list:
    """Синтаксический анализ: преобразование плоского списка токенов в AST (Abstract Syntax Tree)"""
    parser = LispParser(tokens)
    raw_ast = parser.parse_program()
    return [ast_to_expr(node) for node in raw_ast]

@dataclass
class FunctionInfo:
    name: str
    params: List[str]
    body: List[dict]
    addr: int = -1

@dataclass
class CodegenContext:
    env: dict
    code: List[Instruction] = field(default_factory=list)
    stack_depth: int = 0
    current_func: Optional[FunctionInfo] = None
    pending_calls: List[Tuple[int, str]] = field(default_factory=list)

    def emit(self, opcode: Opcode, mode: AddressingMode = AddressingMode.IMMEDIATE, arg: int = 0) -> int:
        self.code.append(Instruction(opcode, mode, arg))
        return len(self.code) - 1

    def patch(self, idx: int, arg: int) -> None:
        inst = self.code[idx]
        self.code[idx] = Instruction(inst.opcode, inst.mode, arg)

    def emit_push(self) -> None:
        self.emit(Opcode.PUSH, AddressingMode.IMMEDIATE, 0)
        self.stack_depth += 1

    def emit_pop(self) -> None:
        self.emit(Opcode.POP, AddressingMode.IMMEDIATE, 0)
        self.stack_depth -= 1

def semantic_analysis(ast: list) -> dict:
    """Семантический анализ: таблицы символов, адреса строк (cstr), вычисление отступов переменных (SP)"""
    globals_map: Dict[str, int] = {}
    global_inits: Dict[str, Optional[dict]] = {}
    var_types: Dict[str, str] = {}
    functions: Dict[str, FunctionInfo] = {}
    strings: Dict[str, int] = {}
    data_section: List[int] = []

    def alloc_string(value: str) -> int:
        if value in strings:
            return strings[value]
        addr = len(data_section)
        strings[value] = addr
        for ch in value:
            data_section.append(ord(ch))
        data_section.append(0)
        return addr

    def collect_strings(node: dict) -> None:
        if isinstance(node, dict):
            if node.get("type") == "string":
                alloc_string(node["value"])
                return
            for key in ("expr", "cond", "then", "else", "value", "port", "left", "right"):
                if key in node and node[key] is not None:
                    collect_strings(node[key])
            if "body" in node:
                for item in node["body"]:
                    collect_strings(item)
            if "args" in node:
                for item in node["args"]:
                    collect_strings(item)

    for node in ast:
        if not isinstance(node, dict):
            continue
        if node.get("type") == "defvar":
            name = node["name"]
            if name in globals_map:
                raise ValueError(f"Duplicate global variable: {name}")
            globals_map[name] = GLOBAL_BASE + len(globals_map)
            global_inits[name] = node.get("expr")
            if isinstance(node.get("expr"), dict) and node["expr"].get("type") == "string":
                var_types[name] = "string"
        elif node.get("type") == "defun":
            fname = node["name"]
            if fname in functions:
                raise ValueError(f"Duplicate function: {fname}")
            params = [p for p in node.get("params", [])]
            functions[fname] = FunctionInfo(fname, params, node.get("body", []))

        collect_strings(node)

    data_len = len(data_section)
    if data_len < GLOBAL_BASE:
        data_section.extend([0] * (GLOBAL_BASE - data_len))

    max_global_addr = max(globals_map.values(), default=GLOBAL_BASE - 1)
    if len(data_section) <= max_global_addr:
        data_section.extend([0] * (max_global_addr + 1 - len(data_section)))

    for name, addr in globals_map.items():
        expr = global_inits.get(name)
        if isinstance(expr, dict) and expr.get("type") == "number":
            data_section[addr] = expr["value"]
            var_types[name] = "number"
        elif isinstance(expr, dict) and expr.get("type") == "string":
            data_section[addr] = strings[expr["value"]]
            var_types[name] = "string"
        else:
            data_section[addr] = 0

    scratch_ret = GLOBAL_BASE + len(globals_map)
    scratch_ptr = scratch_ret + 1
    max_addr = scratch_ptr + 1
    if len(data_section) < max_addr:
        data_section.extend([0] * (max_addr - len(data_section)))

    return {
        "globals": globals_map,
        "global_inits": global_inits,
        "functions": functions,
        "strings": strings,
        "data_section": data_section,
        "var_types": var_types,
        "scratch_ret": scratch_ret,
        "scratch_ptr": scratch_ptr,
    }

def generate_code(ast: list, env: dict) -> tuple[list[Instruction], list[int]]:
    ctx = CodegenContext(env=env)

    entry_jump = ctx.emit(Opcode.JMP, AddressingMode.DIRECT, 0)

    for fname, finfo in env["functions"].items():
        finfo.addr = len(ctx.code)
        ctx.current_func = finfo
        ctx.stack_depth = 0
        compile_function(finfo, ctx)
        ctx.current_func = None

    main_start = len(ctx.code)

    for name, expr in env["global_inits"].items():
        if expr is None:
            continue
        if isinstance(expr, dict) and expr.get("type") in ("number", "string"):
            continue
        compile_expr(expr, ctx)
        emit_store_var(ctx, name)

    for node in ast:
        if not isinstance(node, dict):
            continue
        if node.get("type") in ("defun", "defvar"):
            continue
        compile_stmt(node, ctx)

    ctx.emit(Opcode.HALT, AddressingMode.IMMEDIATE, 0)

    ctx.patch(entry_jump, main_start)
    for idx, fname in ctx.pending_calls:
        if fname not in env["functions"]:
            raise ValueError(f"Unknown function: {fname}")
        ctx.patch(idx, env["functions"][fname].addr)

    return ctx.code, env["data_section"]

def compile_function(finfo: FunctionInfo, ctx: CodegenContext) -> None:
    for stmt in finfo.body:
        compile_stmt(stmt, ctx)
    ctx.emit(Opcode.RET, AddressingMode.IMMEDIATE, 0)

def compile_stmt(stmt: dict, ctx: CodegenContext) -> None:
    stype = stmt.get("type")
    if stype == "setq":
        compile_expr(stmt["expr"], ctx)
        emit_store_var(ctx, stmt["name"])
        return
    if stype == "print":
        compile_print(stmt["value"], ctx)
        return
    if stype == "out":
        compile_out(stmt, ctx)
        return
    if stype == "if":
        compile_if(stmt, ctx)
        return
    if stype == "loop":
        compile_loop(stmt, ctx)
        return
    if stype == "return":
        compile_expr(stmt["expr"], ctx)
        if ctx.current_func is None:
            ctx.emit(Opcode.HALT, AddressingMode.IMMEDIATE, 0)
        else:
            ctx.emit(Opcode.RET, AddressingMode.IMMEDIATE, 0)
        return
    if stype in ("binop", "call", "in", "number", "string", "var"):
        compile_expr(stmt, ctx)
        return

def compile_expr(expr: dict, ctx: CodegenContext) -> None:
    etype = expr.get("type")
    if etype == "number":
        ctx.emit(Opcode.LD, AddressingMode.IMMEDIATE, expr["value"])
        return
    if etype == "string":
        addr = ctx.env["strings"][expr["value"]]
        ctx.emit(Opcode.LD, AddressingMode.IMMEDIATE, addr)
        return
    if etype == "var":
        emit_load_var(ctx, expr["name"])
        return
    if etype == "in":
        port = expr["port"]
        if port.get("type") != "number":
            raise ValueError("Port in (in ...) must be a number literal")
        ctx.emit(Opcode.IN, AddressingMode.IMMEDIATE, port["value"])
        return
    if etype == "out":
        compile_out(expr, ctx)
        return
    if etype == "print":
        compile_print(expr["value"], ctx)
        return
    if etype == "call":
        compile_call(expr, ctx)
        return
    if etype == "binop":
        compile_binop(expr, ctx)
        return
    if etype == "return":
        compile_expr(expr["expr"], ctx)
        if ctx.current_func is None:
            ctx.emit(Opcode.HALT, AddressingMode.IMMEDIATE, 0)
        else:
            ctx.emit(Opcode.RET, AddressingMode.IMMEDIATE, 0)
        return
    if etype == "if":
        compile_if(expr, ctx)
        return
    if etype == "loop":
        compile_loop(expr, ctx)
        return
    raise ValueError(f"Unknown expression type: {etype}")

def emit_load_var(ctx: CodegenContext, name: str) -> None:
    globals_map = ctx.env["globals"]
    if name in globals_map:
        ctx.emit(Opcode.LD, AddressingMode.DIRECT, globals_map[name])
        return
    if ctx.current_func is None:
        raise ValueError(f"Unknown variable: {name}")
    offsets = get_param_offsets(ctx.current_func)
    if name not in offsets:
        raise ValueError(f"Unknown variable: {name}")
    arg = offsets[name] + ctx.stack_depth
    ctx.emit(Opcode.LD, AddressingMode.RELATIVE, arg)

def emit_store_var(ctx: CodegenContext, name: str) -> None:
    globals_map = ctx.env["globals"]
    if name in globals_map:
        ctx.emit(Opcode.ST, AddressingMode.DIRECT, globals_map[name])
        return
    if ctx.current_func is None:
        raise ValueError(f"Unknown variable: {name}")
    offsets = get_param_offsets(ctx.current_func)
    if name not in offsets:
        raise ValueError(f"Unknown variable: {name}")
    arg = offsets[name] + ctx.stack_depth
    ctx.emit(Opcode.ST, AddressingMode.RELATIVE, arg)

def get_param_offsets(finfo: FunctionInfo) -> Dict[str, int]:
    offsets = {}
    n = len(finfo.params)
    for i, name in enumerate(finfo.params):
        offsets[name] = n - i + 1
    return offsets

def compile_binop(expr: dict, ctx: CodegenContext) -> None:
    op = expr["op"]
    if op in ("+", "*"):
        compile_expr(expr["left"], ctx)
        ctx.emit_push()
        compile_expr(expr["right"], ctx)
        opcode = Opcode.ADD if op == "+" else Opcode.MUL
        ctx.emit(opcode, AddressingMode.RELATIVE, 1)
        ctx.emit(Opcode.ST, AddressingMode.RELATIVE, 1)
        ctx.emit_pop()
        return
    if op in ("-", "/", "mod"):
        compile_expr(expr["right"], ctx)
        ctx.emit_push()
        compile_expr(expr["left"], ctx)
        opcode = {"-": Opcode.SUB, "/": Opcode.DIV, "mod": Opcode.MOD}[op]
        ctx.emit(opcode, AddressingMode.RELATIVE, 1)
        ctx.emit(Opcode.ST, AddressingMode.RELATIVE, 1)
        ctx.emit_pop()
        return
    if op in ("=", "!=", "<", ">"):
        compile_cmp(expr, ctx)
        return
    raise ValueError(f"Unknown binop: {op}")

def compile_cmp(expr: dict, ctx: CodegenContext) -> None:
    op = expr["op"]
    compile_expr(expr["right"], ctx)
    ctx.emit_push()
    compile_expr(expr["left"], ctx)
    ctx.emit(Opcode.CMP, AddressingMode.RELATIVE, 1)
    ctx.emit(Opcode.ST, AddressingMode.RELATIVE, 1)
    ctx.emit_pop()

    jmp_true = {
        "=": Opcode.JZ,
        "!=": Opcode.JNZ,
        "<": Opcode.JLT,
        ">": Opcode.JGT,
    }[op]

    jmp_true_idx = ctx.emit(jmp_true, AddressingMode.DIRECT, 0)
    ctx.emit(Opcode.LD, AddressingMode.IMMEDIATE, 0)
    jmp_end_idx = ctx.emit(Opcode.JMP, AddressingMode.DIRECT, 0)
    true_addr = len(ctx.code)
    ctx.emit(Opcode.LD, AddressingMode.IMMEDIATE, 1)
    end_addr = len(ctx.code)
    ctx.patch(jmp_true_idx, true_addr)
    ctx.patch(jmp_end_idx, end_addr)

def compile_call(expr: dict, ctx: CodegenContext) -> None:
    args = expr.get("args", [])
    for arg in args:
        compile_expr(arg, ctx)
        ctx.emit_push()

    call_idx = ctx.emit(Opcode.CALL, AddressingMode.DIRECT, 0)
    ctx.pending_calls.append((call_idx, expr["name"]))

    if args:
        ctx.emit(Opcode.ST, AddressingMode.DIRECT, ctx.env["scratch_ret"])
        for _ in args:
            ctx.emit_pop()
        ctx.emit(Opcode.LD, AddressingMode.DIRECT, ctx.env["scratch_ret"])

def compile_if(expr: dict, ctx: CodegenContext) -> None:
    compile_expr(expr["cond"], ctx)
    ctx.emit(Opcode.CMP, AddressingMode.IMMEDIATE, 0)
    jz_idx = ctx.emit(Opcode.JZ, AddressingMode.DIRECT, 0)
    compile_expr(expr["then"], ctx)
    jmp_end_idx = ctx.emit(Opcode.JMP, AddressingMode.DIRECT, 0)
    else_addr = len(ctx.code)
    if expr.get("else") is not None:
        compile_expr(expr["else"], ctx)
    else:
        ctx.emit(Opcode.LD, AddressingMode.IMMEDIATE, 0)
    end_addr = len(ctx.code)
    ctx.patch(jz_idx, else_addr)
    ctx.patch(jmp_end_idx, end_addr)

def compile_loop(expr: dict, ctx: CodegenContext) -> None:
    start_addr = len(ctx.code)
    for stmt in expr.get("body", []):
        compile_stmt(stmt, ctx)
    ctx.emit(Opcode.JMP, AddressingMode.DIRECT, start_addr)

def compile_print(expr: dict, ctx: CodegenContext) -> None:
    if expr.get("type") == "string":
        compile_print_cstr(expr, ctx)
        return
    if expr.get("type") == "var":
        name = expr["name"]
        if ctx.env["var_types"].get(name) == "string":
            compile_print_cstr(expr, ctx)
            return
    compile_expr(expr, ctx)
    ctx.emit(Opcode.OUT, AddressingMode.IMMEDIATE, 0)

def compile_print_cstr(expr: dict, ctx: CodegenContext) -> None:
    compile_expr(expr, ctx)
    ctx.emit(Opcode.ST, AddressingMode.DIRECT, ctx.env["scratch_ptr"])

    loop_start = len(ctx.code)
    ctx.emit(Opcode.LD, AddressingMode.INDIRECT, ctx.env["scratch_ptr"])
    ctx.emit(Opcode.CMP, AddressingMode.IMMEDIATE, 0)
    jz_idx = ctx.emit(Opcode.JZ, AddressingMode.DIRECT, 0)
    ctx.emit(Opcode.OUT, AddressingMode.IMMEDIATE, 0)
    ctx.emit(Opcode.LD, AddressingMode.DIRECT, ctx.env["scratch_ptr"])
    ctx.emit(Opcode.ADD, AddressingMode.IMMEDIATE, 1)
    ctx.emit(Opcode.ST, AddressingMode.DIRECT, ctx.env["scratch_ptr"])
    ctx.emit(Opcode.JMP, AddressingMode.DIRECT, loop_start)

    end_addr = len(ctx.code)
    ctx.patch(jz_idx, end_addr)
    ctx.emit(Opcode.LD, AddressingMode.DIRECT, ctx.env["scratch_ptr"])

def compile_out(expr: dict, ctx: CodegenContext) -> None:
    port = expr["port"]
    if port.get("type") != "number":
        raise ValueError("Port in (out ...) must be a number literal")
    compile_expr(expr["value"], ctx)
    ctx.emit(Opcode.OUT, AddressingMode.IMMEDIATE, port["value"])

def main():
    if len(sys.argv) < 3:
        print("Usage: python translator.py <input.lisp> <target.bin> [target.asm]")
        return
        
    source_file = sys.argv[1]
    target_bin = sys.argv[2]
    target_asm = sys.argv[3] if len(sys.argv) > 3 else None

    with open(source_file, "r", encoding="utf-8") as f:
        source_code = f.read()

    tokens = tokenize(source_code)
    ast = parse(tokens)
    env = semantic_analysis(ast)
    instructions, data_section = generate_code(ast, env)
    
    write_binary(target_bin, instructions, data_section)
    print(f"Compilation successful. Generated {len(instructions)} instructions.")

    if target_asm:
        with open(target_asm, "w", encoding="utf-8") as asmf:
            asmf.write("ADDR - WORD - ASM\n")
            asmf.write("-----------------------------\n")
            for idx, inst in enumerate(instructions):
                word = inst.encode()
                asmf.write(
                    f"{idx:04X} - {word:08X} - {inst.opcode.name} {inst.mode.name} {inst.arg}\n"
                )

if __name__ == '__main__':
    main()