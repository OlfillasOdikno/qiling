#!/usr/bin/env python3
# 
# Cross Platform and Multi Architecture Advanced Binary Emulation Framework
#

from functools import cached_property

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_MODE_THUMB, UC_MODE_BIG_ENDIAN
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM, KS_MODE_THUMB

from qiling import Qiling
from qiling.const import QL_ARCH, QL_ENDIAN
from qiling.arch.arch import QlArch
from qiling.arch import arm_const
from qiling.arch.register import QlRegisterManager
from qiling.exception import QlErrorArch

class QlArchARM(QlArch):
    bits = 32

    def __init__(self, ql: Qiling):
        super().__init__(ql)

        self.arm_get_tls_addr = 0xFFFF0FE0

    @cached_property
    def uc(self) -> Uc:
        if self.ql.archendian == QL_ENDIAN.EB:
            mode = UC_MODE_ARM + UC_MODE_BIG_ENDIAN

        elif self.ql.archtype == QL_ARCH.ARM_THUMB:
            mode = UC_MODE_THUMB

        elif self.ql.archtype == QL_ARCH.ARM:
            mode = UC_MODE_ARM

        else:
            raise QlErrorArch(f'unsupported arch type {self.ql.archtype}')

        return Uc(UC_ARCH_ARM, mode)

    @cached_property
    def regs(self) -> QlRegisterManager:
        regs_map = arm_const.reg_map
        pc_reg = 'pc'
        sp_reg = 'sp'

        return QlRegisterManager(self.uc, regs_map, pc_reg, sp_reg)

    # get PC
    def get_pc(self) -> int:
        append = 1 if self.check_thumb() == UC_MODE_THUMB else 0

        return self.ql.arch.regs.pc + append

    def __is_thumb(self) -> bool:
        cpsr_v = {
            QL_ENDIAN.EL : 0b100000,
            QL_ENDIAN.EB : 0b100000   # FIXME: should be: 0b000000
        }[self.ql.archendian]

        return bool(self.ql.arch.regs.cpsr & cpsr_v)

    @property
    def disassembler(self) -> Cs:
        # note: we do not cache the disassembler instance; rather we refresh it
        # each time to make sure thumb mode is taken into account

        if self.ql.archtype == QL_ARCH.ARM:
            # FIXME: mode should take endianess into account
            mode = CS_MODE_THUMB if self.__is_thumb() else CS_MODE_ARM

        elif self.ql.archtype == QL_ARCH.ARM_THUMB:
            mode = CS_MODE_THUMB

        else:
            raise QlErrorArch(f'unexpected arch type {self.ql.archtype}')

        return Cs(CS_ARCH_ARM, mode)


    @property
    def assembler(self) -> Ks:
        # note: we do not cache the assembler instance; rather we refresh it
        # each time to make sure thumb mode is taken into account

        if self.ql.archtype == QL_ARCH.ARM:
            # FIXME: mode should take endianess into account
            mode = KS_MODE_THUMB if self.__is_thumb() else KS_MODE_ARM

        elif self.ql.archtype == QL_ARCH.ARM_THUMB:
            mode = KS_MODE_THUMB

        else:
            raise QlErrorArch(f'unexpected arch type {self.ql.archtype}')

        return Ks(KS_ARCH_ARM, mode)

    def enable_vfp(self) -> None:
        self.ql.arch.regs.c1_c0_2 = self.ql.arch.regs.c1_c0_2 | (0xf << 20)

        if self.ql.archendian == QL_ENDIAN.EB:
            self.ql.arch.regs.fpexc = 0x40000000
            #self.ql.arch.regs.fpexc = 0x00000040
        else:
            self.ql.arch.regs.fpexc = 0x40000000

    def check_thumb(self):
        return UC_MODE_THUMB if self.__is_thumb() else UC_MODE_ARM

    """
    set_tls
    """
    def init_get_tls(self):
        self.ql.mem.map(0xFFFF0000, 0x1000, info="[arm_tls]")
        """
        'adr r0, data; ldr r0, [r0]; mov pc, lr; data:.ascii "\x00\x00"'
        """
        sc = b'\x04\x00\x8f\xe2\x00\x00\x90\xe5\x0e\xf0\xa0\xe1\x00\x00\x00\x00'

        # if ql.archendian == QL_ENDIAN.EB:
        #    sc = swap_endianess(sc)

        self.ql.mem.write(self.arm_get_tls_addr, sc)
        self.ql.log.debug("Set init_kernel_get_tls")    

    def swap_endianess(self, s: bytes, blksize=4) -> bytes:
        blocks = (s[i:i + blksize] for i in range(0, len(s), blksize))

        return b''.join(bytes(reversed(b)) for b in blocks)