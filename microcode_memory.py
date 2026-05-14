from dataclasses import dataclass
from isa import Opcode, AddressingMode

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
        mux_sel = ((self.mux_a & 0x3) << 1) | (self.mux_b & 0x1)
        return (
            ((self.latch_ctrl & 0x3) << 22)
            | ((self.alu_op & 0x7) << 19)
            | ((mux_sel & 0x7) << 16)
            | ((self.mem_port & 0x7) << 13)
            | ((self.reg_en & 0x7) << 10)
            | ((self.cond & 0xF) << 6)
            | (self.next_micro_addr & 0x3F)
        )

class ControlUnit:
    def __init__(self):
        # ROM микрокода (слова по 24 бита)
        self.micro_rom = self._initialize_micro_rom()
        self.multi_step_ops = {
            Opcode.PUSH,
            Opcode.POP,
            Opcode.CALL,
            Opcode.RET,
        }
        self.mem_ops = {Opcode.LD, Opcode.ST, Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DIV, Opcode.MOD, Opcode.CMP}
        self.uaddr_map = {opcode: (opcode.value & 0x3F) for opcode in Opcode}

    def _initialize_micro_rom(self):
        # Здесь будет инициализирована таблица микрокоманд для инструкций
        # В pipeline архитектуре этот блок выдает управляющие сигналы (24-bit) для текущего Opcode
        rom = {}
        # rom[Opcode.ADD] = MicrocodeSignal(...)
        return rom

    def get_signals(self, opcode: Opcode) -> MicrocodeSignal:
        return self.micro_rom.get(opcode, MicrocodeSignal())

    def get_micro_steps(self, opcode: Opcode, mode: AddressingMode) -> list[MicrocodeSignal]:
        stall = 1
        flush = 2
        latch_none = 0

        def step(**kwargs) -> MicrocodeSignal:
            return MicrocodeSignal(**kwargs)

        if opcode == Opcode.HALT:
            return [step(latch_ctrl=flush, reg_en=0)]

        if opcode in (Opcode.LD, Opcode.ST) and mode == AddressingMode.INDIRECT:
            return [
                step(latch_ctrl=stall, mem_port=1),
                step(latch_ctrl=latch_none, mem_port=1 if opcode == Opcode.LD else 2, reg_en=1 if opcode == Opcode.LD else 0),
            ]

        if opcode == Opcode.PUSH:
            return [step(latch_ctrl=stall, mem_port=2, reg_en=2), step(latch_ctrl=latch_none)]

        if opcode == Opcode.POP:
            return [step(latch_ctrl=stall, mem_port=1, reg_en=2), step(latch_ctrl=latch_none, reg_en=1)]

        if opcode == Opcode.CALL:
            return [step(latch_ctrl=stall, mem_port=2, reg_en=2), step(latch_ctrl=flush, reg_en=3)]

        if opcode == Opcode.RET:
            return [step(latch_ctrl=stall, mem_port=1, reg_en=2), step(latch_ctrl=flush, reg_en=3)]

        if opcode == Opcode.IN:
            return [step(mem_port=3, reg_en=1)]

        if opcode == Opcode.OUT:
            return [step(mem_port=4)]

        if opcode in (Opcode.JMP, Opcode.JZ, Opcode.JNZ, Opcode.JLT, Opcode.JGT):
            cond_map = {
                Opcode.JMP: 0,
                Opcode.JZ: 1,
                Opcode.JNZ: 2,
                Opcode.JLT: 3,
                Opcode.JGT: 4,
            }
            return [step(latch_ctrl=flush, reg_en=3, cond=cond_map[opcode])]

        alu_map = {
            Opcode.ADD: 1,
            Opcode.SUB: 2,
            Opcode.MUL: 3,
            Opcode.DIV: 4,
            Opcode.MOD: 5,
            Opcode.CMP: 6,
        }
        if opcode in alu_map:
            return [step(alu_op=alu_map[opcode], reg_en=1)]

        if opcode == Opcode.LD:
            return [step(mem_port=1, reg_en=1)]

        if opcode == Opcode.ST:
            return [step(mem_port=2)]

        return [MicrocodeSignal()]

    def get_micro_uaddr(self, opcode: Opcode, step_idx: int) -> int:
        base = self.uaddr_map.get(opcode, 0)
        return (base + step_idx) & 0x3F

    def get_step_count(self, opcode: Opcode, mode: AddressingMode) -> int:
        if opcode in self.multi_step_ops:
            return 2
        if opcode in self.mem_ops and mode == AddressingMode.INDIRECT:
            return 2
        return 1
