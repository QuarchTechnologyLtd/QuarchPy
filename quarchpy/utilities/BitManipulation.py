#!/usr/bin/python
"""
Implements functions for manipulating bits and bytes
"""

'''
setBit(hexString,bit)

    Takes a hex string 0xHHHH or HHHH and sets the specified bit
    returns a 16 bit hex string in form 0xHHHH
'''
def setBit(hexString,bit):
    newVal = int(hexString,16) | 2**bit
    return '0x{:04x}'.format(newVal)

'''
clearBit(hexString,bit)

    Takes a hex string 0xHHHH or HHHH and clears the specified bit
    returns a 16 bit hex string in form 0xHHHH
'''
def clearBit(hexString,bit):
    mask = ((2**16)-1 - (2**bit))
    newVal = int(hexString,16) & mask
    return '0x{:04x}'.format(newVal)

'''
checkBit(hexString,bit)

    Takes a hex string 0xHHHH or HHHH and returns the state of the specified bit
'''
def checkBit(hexString,bit):

    # convert string to an integer
    Val = int(hexString,16)
    # and that integer with the bit mask we want and if anything is left return True
    if Val & 2**bit:
        return True
    else:
        return False