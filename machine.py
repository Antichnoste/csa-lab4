import sys
from dataclasses import dataclass, field

from isa import AddressingMode, Instruction, Opcode, read_binary

@dataclass
class MicrocodeSignal:
    latch_ctrl: int = 0
    alu_op: int = 0
    mux_a: int = 0
    mux_b: int = 0
    mem_port: int = 0
    reg_en: int = 0
    cond: int = 0
    next_micro_addr: int = 0

    def encode(self) -> int:
        return (
            ((self.latch_ctrl & 0x3) << 23)
            | ((self.alu_op & 0x7) << 20)
            | ((self.mux_a & 0x3) << 18)
            | ((self.mux_b & 0x3) << 16)
            | ((self.mem_port & 0x7) << 13)
            | ((self.reg_en & 0x7) << 10)
            | ((self.cond & 0xF) << 6)
            | (self.next_micro_addr & 0x3F)
        )
class ControlUnit:
    def __init__(self):
        self.micro_rom = self._initialize_micro_rom()

    def _initialize_micro_rom(self) -> dict[int, MicrocodeSignal]:
        rom = {}
        stall, flush, latch_none = 1, 2, 0

        def step(**kwargs) -> MicrocodeSignal:
            return MicrocodeSignal(**kwargs)

        rom[0] = step(next_micro_addr=0)

        # 1: HALT
        rom[1] = step(latch_ctrl=flush, reg_en=0, next_micro_addr=0)

        # 10: LD Immediate
        rom[10] = step(mux_b=0, reg_en=1, next_micro_addr=0)
        
        # 11: LD Direct
        rom[11] = step(mem_port=1, mux_a=0, mux_b=1, reg_en=1, next_micro_addr=0)
        
        # 12: LD Relative
        rom[12] = step(mem_port=1, mux_a=1, mux_b=1, reg_en=1, next_micro_addr=0)
        
        # 13-14: LD Indirect (2 такта)
        rom[13] = step(latch_ctrl=stall, mem_port=1, mux_a=0, next_micro_addr=14) # Такт 1: Чтение адреса в BR
        rom[14] = step(latch_ctrl=latch_none, mem_port=1, mux_a=2, mux_b=1, reg_en=1, next_micro_addr=0) # Такт 2: Чтение данных по BR

        # 15: ST Direct
        rom[15] = step(mem_port=2, mux_a=0, next_micro_addr=0)
        
        # 16: ST Relative
        rom[16] = step(mem_port=2, mux_a=1, next_micro_addr=0)
        
        # 17-18: ST Indirect (2 такта)
        rom[17] = step(latch_ctrl=stall, mem_port=1, mux_a=0, next_micro_addr=18) # Такт 1: Чтение адреса в BR
        rom[18] = step(latch_ctrl=latch_none, mem_port=2, mux_a=2, next_micro_addr=0) # Такт 2: Пишем ACC по BR
        
        # --- ADD ---
        rom[20] = step(alu_op=1, mux_b=0, reg_en=1, next_micro_addr=0) # ADD Immediate (MUX B = 0)
        rom[21] = step(mem_port=1, alu_op=1, mux_a=0, mux_b=1, reg_en=1, next_micro_addr=0) # ADD Direct (MUX B = 1)
        rom[22] = step(mem_port=1, alu_op=1, mux_a=1, mux_b=1, reg_en=1, next_micro_addr=0) # ADD Relative (MUX B = 1)

        # --- SUB ---
        rom[23] = step(alu_op=2, mux_b=0, reg_en=1, next_micro_addr=0) # SUB Immediate
        rom[24] = step(mem_port=1, alu_op=2, mux_a=0, mux_b=1, reg_en=1, next_micro_addr=0) # SUB Direct
        rom[25] = step(mem_port=1, alu_op=2, mux_a=1, mux_b=1, reg_en=1, next_micro_addr=0) # SUB Relative

        # --- MUL ---
        rom[26] = step(alu_op=3, mux_b=0, reg_en=1, next_micro_addr=0) # MUL Immediate
        rom[27] = step(mem_port=1, alu_op=3, mux_a=0, mux_b=1, reg_en=1, next_micro_addr=0) # MUL Direct
        rom[28] = step(mem_port=1, alu_op=3, mux_a=1, mux_b=1, reg_en=1, next_micro_addr=0) # MUL Relative

        # --- DIV ---
        rom[29] = step(alu_op=4, mux_b=0, reg_en=1, next_micro_addr=0) # DIV Immediate
        rom[30] = step(mem_port=1, alu_op=4, mux_a=0, mux_b=1, reg_en=1, next_micro_addr=0) # DIV Direct
        rom[31] = step(mem_port=1, alu_op=4, mux_a=1, mux_b=1, reg_en=1, next_micro_addr=0) # DIV Relative

        # --- MOD ---
        rom[32] = step(alu_op=5, mux_b=0, reg_en=1, next_micro_addr=0) # MOD Immediate
        rom[33] = step(mem_port=1, alu_op=5, mux_a=0, mux_b=1, reg_en=1, next_micro_addr=0) # MOD Direct
        rom[34] = step(mem_port=1, alu_op=5, mux_a=1, mux_b=1, reg_en=1, next_micro_addr=0) # MOD Relative

        # --- CMP ---
        rom[35] = step(alu_op=6, mux_b=0, reg_en=0, next_micro_addr=0) # CMP Immediate
        rom[36] = step(mem_port=1, alu_op=6, mux_a=0, mux_b=1, reg_en=0, next_micro_addr=0) # CMP Direct
        rom[37] = step(mem_port=1, alu_op=6, mux_a=1, mux_b=1, reg_en=0, next_micro_addr=0) # CMP Relative
        
        # 40-41: PUSH (2 такта)
        rom[40] = step(latch_ctrl=stall, mem_port=2, mux_a=1, next_micro_addr=41)
        rom[41] = step(latch_ctrl=latch_none, reg_en=3, next_micro_addr=0) # SP DEC

        # 42-43: POP (2 такта)
        rom[42] = step(latch_ctrl=stall, mem_port=1, reg_en=2, mux_a=1, next_micro_addr=43) # SP INC
        rom[43] = step(latch_ctrl=latch_none, reg_en=1, mux_b=1, next_micro_addr=0) # Запись в ACC

        # 44-45: CALL (2 такта)
        rom[44] = step(latch_ctrl=stall, mem_port=2, mux_a=1, next_micro_addr=45) # Запись PC в стек по SP
        rom[45] = step(latch_ctrl=flush, reg_en=5, next_micro_addr=0) # PC WE + SP DEC

        # 46-47: RET (2 такта)
        rom[46] = step(latch_ctrl=stall, mem_port=1, reg_en=2, mux_a=1, next_micro_addr=47) # SP INC, чтение DMEM
        rom[47] = step(latch_ctrl=flush, reg_en=4, next_micro_addr=0) # PC WE

        # 48: IN
        rom[48] = step(mem_port=3, reg_en=1, mux_b=2, next_micro_addr=0)
        
        # 49: OUT
        rom[49] = step(mem_port=4, next_micro_addr=0)

        # 50: JUMPS
        rom[50] = step(latch_ctrl=flush, reg_en=4, next_micro_addr=0)

        return rom

    def get_start_uaddr(self, opcode: Opcode, mode: AddressingMode) -> int:
        """Address Mapper. Преобразует Opcode и Mode макрокоманды в стартовый адрес ПЗУ."""
        if opcode == Opcode.LD:
            if mode == AddressingMode.IMMEDIATE: return 10
            if mode == AddressingMode.DIRECT: return 11
            if mode == AddressingMode.RELATIVE: return 12
            if mode == AddressingMode.INDIRECT: return 13
        if opcode == Opcode.ST:
            if mode == AddressingMode.DIRECT: return 15
            if mode == AddressingMode.RELATIVE: return 16
            if mode == AddressingMode.INDIRECT: return 17

        base_math = {
            Opcode.ADD: 20, 
            Opcode.SUB: 23,
            Opcode.MUL: 26,
            Opcode.DIV: 29,
            Opcode.MOD: 32,
            Opcode.CMP: 35
        }
        if opcode in base_math:
            base = base_math[opcode]
            if mode == AddressingMode.IMMEDIATE: return base
            if mode == AddressingMode.DIRECT: return base + 1
            if mode == AddressingMode.RELATIVE: return base + 2

        fixed_map = {
            Opcode.HALT: 1,
            Opcode.PUSH: 40,
            Opcode.POP: 42,
            Opcode.CALL: 44,
            Opcode.RET: 46,
            Opcode.IN: 48,
            Opcode.OUT: 49,
        }
        if opcode in fixed_map:
            return fixed_map[opcode]

        if opcode in (Opcode.JMP, Opcode.JZ, Opcode.JNZ, Opcode.JLT, Opcode.JGT):
            return 50

        return 0

@dataclass
class IF_ID_Latch:
    instruction: Instruction = field(default_factory=lambda: Instruction(Opcode.HALT, AddressingMode.IMMEDIATE, 0))
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
        self.upc = 0
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

        if self.id_ex.valid: 
            stall, flush = self.ex_stage()

        if self.if_id.valid and not stall:
            stall = self.id_stage() or stall

        if not stall and not flush: 
            self.if_stage()

        if flush:
            self.if_id.valid = False
            self.id_ex.valid = False
            
        if self.trace:
            self._print_trace(stall, flush)

    def ex_stage(self) -> tuple[bool, bool]:
        if not self.ex_busy:
            self.ex_busy = True
            self.ex_op = self.id_ex.opcode
            self.ex_mode = self.id_ex.mode
            self.ex_arg = self.id_ex.arg
            self.ex_pc = self.id_ex.pc
            
            self.upc = self.cu.get_start_uaddr(self.ex_op, self.ex_mode)
            self.ex_tmp = 0

        current_micro_signal = self.cu.micro_rom.get(self.upc, MicrocodeSignal())

        op = self.ex_op
        mode = self.ex_mode
        arg = self.ex_arg

        if self.micro_trace:
            self._print_micro_trace()

        if op == Opcode.HALT:
            self.halted = True
            self.ex_busy = False
            self.id_ex.valid = False
            return False, False

        if op in (Opcode.LD, Opcode.ST, Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DIV, Opcode.MOD, Opcode.CMP):
            if mode == AddressingMode.INDIRECT and current_micro_signal.next_micro_addr != 0:
                self.ex_tmp = self._read_mem(arg)
                self.upc = current_micro_signal.next_micro_addr
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
            if current_micro_signal.next_micro_addr != 0:
                self._write_mem(self.sp, self.acc)
                self.upc = current_micro_signal.next_micro_addr
                return True, False
            self.sp = (self.sp - 1) & 0xFFFF
            self.ex_busy = False
            self.id_ex.valid = False
            return False, False

        if op == Opcode.POP:
            if current_micro_signal.next_micro_addr != 0:
                self.sp = (self.sp + 1) & 0xFFFF
                self.upc = current_micro_signal.next_micro_addr
                return True, False
            self.acc = self._to_signed32(self._read_mem(self.sp))
            self._update_flags(self.acc)
            self.ex_busy = False
            self.id_ex.valid = False
            return False, False

        if op == Opcode.CALL:
            if current_micro_signal.next_micro_addr != 0:
                ret_addr = (self.ex_pc + 1) & 0xFFFF
                self._write_mem(self.sp, ret_addr)
                self.upc = current_micro_signal.next_micro_addr
                return True, False
            self.sp = (self.sp - 1) & 0xFFFF
            self.pc = arg
            self.ex_busy = False
            self.id_ex.valid = False
            return False, True

        if op == Opcode.RET:
            if current_micro_signal.next_micro_addr != 0:
                self.sp = (self.sp + 1) & 0xFFFF
                self.upc = current_micro_signal.next_micro_addr
                return True, False
            self.pc = self._read_mem(self.sp) & 0xFFFF
            self.ex_busy = False
            self.id_ex.valid = False
            return False, True
        
        if op == Opcode.IN:
            port = arg
            if port != 0:
                self.acc = 0
            if self.input_buffer:
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
            if op == Opcode.JMP: take = True
            elif op == Opcode.JZ: take = (self.flag_z == 1)
            elif op == Opcode.JNZ: take = (self.flag_z == 0)
            elif op == Opcode.JLT: take = (self.flag_n == 1)
            elif op == Opcode.JGT: take = (self.flag_z == 0 and self.flag_n == 0)

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
            f"uPC={self.upc:02} STALL={int(stall)} FLUSH={int(flush)}"
        )
        print(
            f"ACC={self.acc:11} SP={self.sp:04X} Z={self.flag_z} N={self.flag_n} TMP={self.ex_tmp:04X}"
        )
        print(f"IF: {if_inst} | ID: {id_inst} | EX: {ex_inst}")
        print("-" * 72)

    def _print_micro_trace(self) -> None:
        sig = self.cu.micro_rom.get(self.upc, MicrocodeSignal())
        uword = sig.encode()
        print(
            f"[uTICK {self.tick_counter:04}] uPC={self.upc:02X} OP={self.ex_op.name} MODE={self.ex_mode.name} "
            f"UWORD=0x{uword:06X}"
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
    while not machine.halted and machine.tick_counter < 10_000_000:
        machine.tick()
    print(f"Halted! Ticks: {machine.tick_counter}")
    if machine.output_buffer:
        print("Output:", "".join(chr(c) for c in machine.output_buffer))

def main():
    trace = "--trace" in sys.argv[1:]
    micro_trace = "--micro-trace" in sys.argv[1:]
    args = [arg for arg in sys.argv[1:] if arg not in ("--trace", "--micro-trace")]
    if len(args) < 1:
        print("Usage: python machine.py <target.bin> [input.txt] [--trace] [--micro-trace]")
        return
    run_simulation(args[0], args[1] if len(args) > 1 else "", trace=trace, micro_trace=micro_trace)

if __name__ == '__main__':
    main()