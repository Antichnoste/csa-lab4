from dataclasses import dataclass
from isa import Opcode, AddressingMode

@dataclass
class MicrocodeSignal:
    latch_ctrl: int = 0
    mux_a: int = 0
    mux_b: int = 0
    alu_op: int = 0
    next_micro_addr: int = 0

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

    def _initialize_micro_rom(self):
        # Здесь будет инициализирована таблица микрокоманд для инструкций
        # В pipeline архитектуре этот блок выдает управляющие сигналы (24-bit) для текущего Opcode
        rom = {}
        # rom[Opcode.ADD] = MicrocodeSignal(...)
        return rom

    def get_signals(self, opcode: Opcode) -> MicrocodeSignal:
        return self.micro_rom.get(opcode, MicrocodeSignal())

    def get_step_count(self, opcode: Opcode, mode: AddressingMode) -> int:
        if opcode in self.multi_step_ops:
            return 2
        if opcode in self.mem_ops and mode == AddressingMode.INDIRECT:
            return 2
        return 1
