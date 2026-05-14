import sys
from dataclasses import dataclass, field
from isa import read_binary, Opcode, AddressingMode, Instruction
from microcode_memory import ControlUnit

@dataclass
class IF_ID_Latch:
    instruction: Instruction = field(
        default_factory=lambda: Instruction(Opcode.HALT, AddressingMode.IMMEDIATE, 0)
    )
    pc: int = 0
    valid: bool = False

@dataclass
class ID_EX_Latch:
    opcode: Opcode = Opcode.HALT
    mode: AddressingMode = AddressingMode.IMMEDIATE
    arg: int = 0
    sp: int = 0
    acc: int = 0
    pc: int = 0
    valid: bool = False

class Machine:
    def __init__(self, instructions: list[Instruction], data_section: list[int], input_buffer: list[int], trace: bool = False, micro_trace: bool = False):
        self.imem = instructions
        self.dmem = data_section + [0] * (65536 - len(data_section))
        self.acc = 0
        self.pc = 0
        self.sp = 0xFFFF
        self.flag_z = 0
        self.flag_n = 0
        
        self.input_buffer = input_buffer
        self.output_buffer = []
        
        self.if_id = IF_ID_Latch()
        self.id_ex = ID_EX_Latch()
        
        self.tick_counter = 0
        self.halted = False
        self.cu = ControlUnit()
        self.ex_busy = False
        self.ex_step = 0
        self.ex_total = 0
        self.ex_op = Opcode.HALT
        self.ex_mode = AddressingMode.IMMEDIATE
        self.ex_arg = 0
        self.ex_pc = 0
        self.ex_tmp = 0
        self.trace = trace
        self.micro_trace = micro_trace

    def tick(self):
        self.tick_counter += 1
        stall, flush = False, False
        if self.id_ex.valid: stall, flush = self.ex_stage()
        if self.if_id.valid and not stall: stall = self.id_stage() or stall
        if not stall and not flush: self.if_stage()
        if flush:
            self.if_id.valid = False
            self.id_ex.valid = False
        if self.trace:
            self._print_trace(stall, flush)

    def ex_stage(self) -> tuple[bool, bool]:
        if not self.ex_busy:
            self.ex_busy = True
            self.ex_step = 0
            self.ex_op = self.id_ex.opcode
            self.ex_mode = self.id_ex.mode
            self.ex_arg = self.id_ex.arg
            self.ex_pc = self.id_ex.pc
            self.ex_total = self.cu.get_step_count(self.ex_op, self.ex_mode)
            self.ex_tmp = 0

        if self.micro_trace:
            self._print_micro_trace()

        op = self.ex_op
        mode = self.ex_mode
        arg = self.ex_arg

        if op == Opcode.HALT:
            self.halted = True
            self.ex_busy = False
            self.id_ex.valid = False
            return False, False

        if op in (Opcode.LD, Opcode.ST, Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DIV, Opcode.MOD, Opcode.CMP):
            if mode == AddressingMode.INDIRECT and self.ex_step == 0:
                self.ex_tmp = self._read_mem(arg)
                self.ex_step += 1
                return True, False

            operand = self._load_operand(mode, arg)
            if op == Opcode.LD:
                self.acc = self._to_signed32(operand)
                self._update_flags(self.acc)
            elif op == Opcode.ST:
                addr = self._store_address(mode, arg)
                self._write_mem(addr, self.acc)
            elif op == Opcode.ADD:
                self.acc = self._to_signed32(self.acc + operand)
                self._update_flags(self.acc)
            elif op == Opcode.SUB:
                self.acc = self._to_signed32(self.acc - operand)
                self._update_flags(self.acc)
            elif op == Opcode.MUL:
                self.acc = self._to_signed32(self.acc * operand)
                self._update_flags(self.acc)
            elif op == Opcode.DIV:
                self.acc = self._to_signed32(self.acc // operand if operand != 0 else 0)
                self._update_flags(self.acc)
            elif op == Opcode.MOD:
                self.acc = self._to_signed32(self.acc % operand if operand != 0 else 0)
                self._update_flags(self.acc)
            elif op == Opcode.CMP:
                diff = self._to_signed32(self.acc - operand)
                self._update_flags(diff)

            self.ex_busy = False
            self.id_ex.valid = False
            return False, False

        if op == Opcode.PUSH:
            if self.ex_step == 0:
                self._write_mem(self.sp, self.acc)
                self.ex_step += 1
                return True, False
            self.sp = (self.sp - 1) & 0xFFFF
            self.ex_busy = False
            self.id_ex.valid = False
            return False, False

        if op == Opcode.POP:
            if self.ex_step == 0:
                self.sp = (self.sp + 1) & 0xFFFF
                self.ex_step += 1
                return True, False
            self.acc = self._to_signed32(self._read_mem(self.sp))
            self._update_flags(self.acc)
            self.ex_busy = False
            self.id_ex.valid = False
            return False, False

        if op == Opcode.CALL:
            if self.ex_step == 0:
                ret_addr = (self.ex_pc + 1) & 0xFFFF
                self._write_mem(self.sp, ret_addr)
                self.ex_step += 1
                return True, False
            self.sp = (self.sp - 1) & 0xFFFF
            self.pc = arg
            self.ex_busy = False
            self.id_ex.valid = False
            return False, True

        if op == Opcode.RET:
            if self.ex_step == 0:
                self.sp = (self.sp + 1) & 0xFFFF
                self.ex_step += 1
                return True, False
            self.pc = self._read_mem(self.sp) & 0xFFFF
            self.ex_busy = False
            self.id_ex.valid = False
            return False, True

        if op == Opcode.IN:
            port = arg
            if port != 0:
                self.acc = 0
            elif self.input_buffer:
                self.acc = self._to_signed32(self.input_buffer.pop(0))
            else:
                self.acc = 0
            self._update_flags(self.acc)
            self.ex_busy = False
            self.id_ex.valid = False
            return False, False

        if op == Opcode.OUT:
            self.output_buffer.append(self.acc)
            self.ex_busy = False
            self.id_ex.valid = False
            return False, False

        if op in (Opcode.JMP, Opcode.JZ, Opcode.JNZ, Opcode.JLT, Opcode.JGT):
            take = False
            if op == Opcode.JMP:
                take = True
            elif op == Opcode.JZ:
                take = self.flag_z == 1
            elif op == Opcode.JNZ:
                take = self.flag_z == 0
            elif op == Opcode.JLT:
                take = self.flag_n == 1
            elif op == Opcode.JGT:
                take = self.flag_z == 0 and self.flag_n == 0

            if take:
                self.pc = arg
            self.ex_busy = False
            self.id_ex.valid = False
            return False, take

        self.ex_busy = False
        self.id_ex.valid = False
        return False, False

    def id_stage(self) -> bool:
        inst = self.if_id.instruction
        self.id_ex.opcode, self.id_ex.mode, self.id_ex.arg = inst.opcode, inst.mode, inst.arg
        self.id_ex.pc = self.if_id.pc
        self.id_ex.valid = True
        return False

    def if_stage(self):
        if self.pc < len(self.imem):
            self.if_id.instruction = self.imem[self.pc]
            self.if_id.pc = self.pc
            self.if_id.valid = True
            self.pc += 1
        else:
            self.if_id.valid = False

    def _to_signed32(self, value: int) -> int:
        value &= 0xFFFFFFFF
        return value if value < 0x80000000 else value - 0x100000000

    def _update_flags(self, value: int) -> None:
        self.flag_z = 1 if value == 0 else 0
        self.flag_n = 1 if value < 0 else 0

    def _read_mem(self, addr: int) -> int:
        addr &= 0xFFFF
        return self.dmem[addr]

    def _write_mem(self, addr: int, value: int) -> None:
        addr &= 0xFFFF
        self.dmem[addr] = self._to_signed32(value)

    def _load_operand(self, mode: AddressingMode, arg: int) -> int:
        if mode == AddressingMode.IMMEDIATE:
            return arg
        if mode == AddressingMode.DIRECT:
            return self._read_mem(arg)
        if mode == AddressingMode.INDIRECT:
            return self._read_mem(self.ex_tmp)
        addr = (self.sp + arg) & 0xFFFF
        return self._read_mem(addr)

    def _store_address(self, mode: AddressingMode, arg: int) -> int:
        if mode == AddressingMode.DIRECT:
            return arg
        if mode == AddressingMode.INDIRECT:
            return self.ex_tmp
        return (self.sp + arg) & 0xFFFF

    def _format_inst(self, opcode: Opcode, mode: AddressingMode, arg: int) -> str:
        return f"{opcode.name} {mode.name} {arg}"

    def _encode_word(self, opcode: Opcode, mode: AddressingMode, arg: int) -> int:
        return ((opcode.value & 0xFF) << 24) | ((mode.value & 0x3) << 22) | (arg & 0x3FFFFF)

    def _print_trace(self, stall: bool, flush: bool) -> None:
        if_inst = self._format_inst(
            self.if_id.instruction.opcode,
            self.if_id.instruction.mode,
            self.if_id.instruction.arg,
        ) if self.if_id.valid else "NOP"

        id_inst = self._format_inst(
            self.id_ex.opcode,
            self.id_ex.mode,
            self.id_ex.arg,
        ) if self.id_ex.valid else "NOP"

        ex_inst = self._format_inst(
            self.ex_op,
            self.ex_mode,
            self.ex_arg,
        ) if self.ex_busy else "NOP"

        ir_word = None
        if self.id_ex.valid:
            ir_word = self._encode_word(self.id_ex.opcode, self.id_ex.mode, self.id_ex.arg)
        elif self.if_id.valid:
            ir_word = self._encode_word(
                self.if_id.instruction.opcode,
                self.if_id.instruction.mode,
                self.if_id.instruction.arg,
            )

        ir_text = f"{ir_word:08X}" if ir_word is not None else "--------"

        print(
            f"[TICK {self.tick_counter:04}] PC={self.pc:04X} IR={ir_text} "
            f"EXSTEP={self.ex_step}/{self.ex_total} STALL={int(stall)} FLUSH={int(flush)}"
        )
        print(
            f"ACC={self.acc:11} SP={self.sp:04X} Z={self.flag_z} N={self.flag_n} TMP={self.ex_tmp:04X}"
        )
        print(f"IF: {if_inst} | ID: {id_inst} | EX: {ex_inst}")
        print("-" * 72)

    def _print_micro_trace(self) -> None:
        steps = self.cu.get_micro_steps(self.ex_op, self.ex_mode)
        step_idx = min(self.ex_step, len(steps) - 1)
        sig = steps[step_idx]
        uaddr = self.cu.get_micro_uaddr(self.ex_op, step_idx)
        uword = sig.encode()
        print(
            f"[uTICK {self.tick_counter:04}] uPC={uaddr:02X} OP={self.ex_op.name} MODE={self.ex_mode.name} "
            f"UWORD=0x{uword:06X} STEP={step_idx + 1}/{len(steps)}"
        )
        print(
            f"LATCH={sig.latch_ctrl} ALU={sig.alu_op} MUXA={sig.mux_a} MUXB={sig.mux_b} "
            f"MEM={sig.mem_port} REG={sig.reg_en} COND={sig.cond} NEXT={sig.next_micro_addr}"
        )

def run_simulation(target_bin: str, input_file: str, trace: bool = False, micro_trace: bool = False):
    instructions, data_section = read_binary(target_bin)
    input_buffer = []
    if input_file:
        with open(input_file, 'r', encoding='utf-8') as f:
            input_buffer = [ord(char) for char in f.read()]
            
    machine = Machine(instructions, data_section, input_buffer, trace=trace, micro_trace=micro_trace)
    print("Start execution...")
    while not machine.halted and machine.tick_counter < 1000:
        machine.tick()
    print(f"Halted! Ticks: {machine.tick_counter}")
    if machine.output_buffer:
        print("Output:", "".join(chr(c) for c in machine.output_buffer))

def main():
    trace = "--trace" in sys.argv[1:]
    micro_trace = "--micro-trace" in sys.argv[1:]
    args = [arg for arg in sys.argv[1:] if arg not in ("--trace", "--micro-trace")]
    if len(args) < 1:
        print("Usage: python cpu_sim.py <target.bin> [input.txt] [--trace] [--micro-trace]")
        return
    run_simulation(args[0], args[1] if len(args) > 1 else "", trace=trace, micro_trace=micro_trace)

if __name__ == '__main__':
    main()
