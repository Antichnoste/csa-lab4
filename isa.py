import struct
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple

class Opcode(int, Enum):
    HALT = 0x00
    LD   = 0x01
    ST   = 0x02
    
    ADD  = 0x10
    SUB  = 0x11
    MUL  = 0x12
    DIV  = 0x13
    MOD  = 0x14
    CMP  = 0x15
    
    JMP  = 0x20
    JZ   = 0x21
    JNZ  = 0x22
    JLT  = 0x23
    JGT  = 0x24
    
    CALL = 0x30
    RET  = 0x31
    PUSH = 0x32
    POP  = 0x33
    
    IN   = 0x40
    OUT  = 0x41

class AddressingMode(int, Enum):
    IMMEDIATE = 0b00  # 0: Операнд прямо в инструкции (#val)
    DIRECT    = 0b01  # 1: Абсолютный адрес в DMEM (addr)
    INDIRECT  = 0b10  # 2: Косвенный адрес ([addr])
    RELATIVE  = 0b11  # 3: Смещение относительно SP (SP + val)

@dataclass
class Instruction:
    opcode: Opcode
    mode: AddressingMode
    arg: int  # 22-битное расширяемое знаковое число

    def encode(self) -> int:
        """
        Превращает инструкцию в 32-битное машинное слово:
        [31:24] - Opcode (8 бит)
        [23:22] - Mode (2 бита)
        [21:0]  - Argument (22 бита, signed)
        """
        enc_opcode = (self.opcode.value & 0xFF) << 24
        enc_mode = (self.mode.value & 0x3) << 22
        enc_arg = self.arg & 0x3FFFFF
        return enc_opcode | enc_mode | enc_arg

    @classmethod
    def decode(cls, word: int) -> 'Instruction':
        """Декодирует 32-битное слово обратно в объект Instruction"""
        opcode_val = (word >> 24) & 0xFF
        mode_val = (word >> 22) & 0x3
        arg = word & 0x3FFFFF
        if arg & (1 << 21):
            arg -= (1 << 22)
            
        return cls(Opcode(opcode_val), AddressingMode(mode_val), arg)

def write_binary(filename: str, instructions: List[Instruction], data_section: List[int]):
    """
    Формат бинарного файла:
    [4 байта] - Количество инструкций (N)
    [4 байта] - Количество слов данных (M)
    [N * 4 байт] - Сами инструкции
    [M * 4 байт] - Сами данные
    """
    with open(filename, "wb") as f:
        f.write(struct.pack(">II", len(instructions), len(data_section)))
        for inst in instructions:
            f.write(struct.pack(">I", inst.encode()))
        for data_word in data_section:
            f.write(struct.pack(">i", data_word))

def read_binary(filename: str) -> Tuple[List[Instruction], List[int]]:
    with open(filename, "rb") as f:
        n_inst, n_data = struct.unpack(">II", f.read(8))
        
        instructions = []
        for _ in range(n_inst):
            word, = struct.unpack(">I", f.read(4))
            instructions.append(Instruction.decode(word))
            
        data_section = []
        for _ in range(n_data):
            word, = struct.unpack(">i", f.read(4))
            data_section.append(word)
            
        return instructions, data_section