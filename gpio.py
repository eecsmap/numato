#!python3

'''
Drive the 8 channel usb gpio module
https://numato.com/product/8-channel-usb-gpio-module-with-analog-inputs/

Reference:
https://numato.com/docs/8-channel-bluetooth-gpio-module/

GPIO ADC
--------
IO0  ADC0
IO1  ADC1
IO2  ADC2
IO3  ADC3
IO4  NA
IO5  NA
IO6  ADC4
IO7  ADC5
GND  GND
'''

import sys
# pip install pyserial
import serial
import time
import argparse
import pytest
import logging
import contextlib

logger = logging.getLogger(__name__)

ADC_MAX = 6

class ADC_IN:

    def __init__(self, gpio):
        self._gpio = gpio
    
    def __getitem__(self, channel):
        return self._gpio._adc_read(channel)

class DIGIT_IN:

    def __init__(self, gpio):
        self._gpio = gpio
    
    def __getitem__(self, channel):
        return self._gpio._gpio_read(channel)

class DIGIT_OUT:
    
    def __init__(self, gpio):
        self._gpio = gpio

    def __setitem__(self, channel, bit):
        self._gpio._gpio_write(channel, bit & 1)

# ===========================================================================
# GPIO
# ===========================================================================
class GPIO:

    ENTER = '\r'

    def __init__(self, port_file):
        logger.debug(f'connecting serial port {port_file} ...')
        self._serial_port = serial.Serial(port_file, 19200, timeout=0)
        logger.debug(f'serial port {port_file} connected.')
        # when powered on
        # register value is 0
        # iodir is all input (0xff)
        # yet mask is kept in ROM
        self._adc_in = ADC_IN(self)
        self._digit_in = DIGIT_IN(self)
        self._digit_out = DIGIT_OUT(self)

    def close(self):
        logger.debug('closing serial port ...')
        self._serial_port.close()
        logger.debug('serial port closed.')

    @property
    def adc_in(self):
        return self._adc_in

    @property
    def digit_in(self):
        return self._digit_in

    @property
    def digit_out(self):
        return self._digit_out

    def _read(self):
        lines = []
        line = None
        # skip empty lines
        while not line:
            line = self._serial_port.readline()
        # read all non-empty lines
        while line:
            logger.debug(f'read: {line}')
            lines.append(line)
            line = self._serial_port.readline()
        # lines[-3] is the command itself
        # lines[-2] is the result, begin with '\r' and end with '\n'
        # lines[-1] is the prompt
        assert len(lines) >= 3, lines
        assert lines[-2].startswith(b'\r'), lines[-2]
        assert lines[-2].endswith(b'\n'), lines[-2]
        return lines[-2][1:-1]

    def _consume(self):
        lines = []
        line = None
        while not line:
            line = self._serial_port.readline()
        while line:
            logger.debug(f'read: {line}')
            lines.append(line)
            line = self._serial_port.readline()
        # lines[-2] is the command itself
        # lines[-1] is the prompt '\r>'
        assert len(lines) >= 2, lines

    def _write(self, s):
        logger.debug(f'write: {s}')
        self._serial_port.write(f'{s}{self.ENTER}'.encode())

    @property
    def value(self):
        '''
        read the status of all GPIO pins
        if a pin is adc reading, the value in correspoding bit is always 0 until the iodir is changed to output
        '''
        self._write('gpio readall')
        return int(self._read(), 16)
    
    @value.setter
    def value(self, v):
        '''
        write to all non-masked output pins
        '''
        v &= 255
        self._write(f'gpio writeall {v:02x}')
        self._consume()

    @property
    def version(self):
        self._write('ver')
        line = self._read()
        return line.decode()

    def _gpio_read(self, channel):
        self._write(f'gpio read {channel}')
        line = self._read()
        return int(line)

    def _gpio_write(self, channel, b):
        cmd = ['clear', 'set'][bool(b)]
        self._write(f'gpio {cmd} {channel}')
        self._consume()

    def _adc_read(self, channel):
        self._write(f'adc read {channel}')
        line = self._read()
        return int(line)

    @property
    def id(self, value=0):
        self._write('id get')
        return self._read().decode()

    @id.setter
    def id(self, value=0):
        if type(value) == int: value = f'{value:08}'
        value = str(value)[:8]
        self._write(f'id set {value:>8}')
        self._consume()

    def __getitem__(self, channel):
        if type(channel) == int and channel in range(8):
            return self.value >> channel & 1

    def __setitem__(self, channel, bit):
        if type(channel) == int and channel in range(8):
            self._gpio_write(channel, bit & 1)

    def set_mask(self, value):
        '''
        affect writeall/iodir
        0 to mask out
        1 to allow operations
        '''
        self._write(f'gpio iomask {value:02x}')
        self._consume()

    def set_iodir(self, value):
        '''
        0 for output, 1 for input
        can be overwirtten by subsequent set/clear/read/adc command
        '''
        self._write(f'gpio iodir {value:02x}')
        self._consume()
        
    def __repr__(self):
        return f'<gpio version: {self.version}; id: {self.id}; bits: {self.value:08b}>'

@contextlib.contextmanager
def open(port_file):
    try:
        g = GPIO(port_file)
        yield g
    except:
        pass
    finally:
        g.close()

# ===========================================================================
# cmd interface
# ===========================================================================

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('port', help='COMx for windows, /dev/ttyUSBx for linux, /dev/tty.usbmodemxxx for mac')
    parser.add_argument('mode', choices=['adc', 'digit'])
    parser.add_argument('channel', type=int)
    parser.add_argument('-v', '--value', type=int, default=None)
    return parser.parse_args()

def main(port, mode, channel, value):
    with open(port) as g:
        if mode == 'adc':
            l = g.adc_in
        if mode == 'digit':
            l = g.digit_out if value else g.digit_in
        if value:
            l[channel] = value
        else:
            print(l[channel])

if __name__ == '__main__':
    logging.basicConfig(level=logging.WARN, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    args = parse_args()
    main(args.port, args.mode, args.channel, args.value)


# digit output has low-impedance, use 1K resisitor on the Pin to device to drive.
# 
# when g.adc_in[0] is reading < 440, g.digit_in[0] normally reads 0.
# unless g.digit_out[0] writes 1 first, where pull-up resistor is used, then
# immediately start a g.digit_in[0], it will get a 1 instead.
# however, if we do a g.adc_in[0] then g.digit_in[0], will get a 0.

# g.value = N will write N & mask into the internal register
# g.value, however, read real value on input mode pins only.

# g.adc_in[n] or g.digit_in[n] will set the corresponding pin to input mode.
# g.digit_out[n] set the pin to output mode.

# g.set_iodir(P) will set internal IO pattern to (P & mask | IO & ~mask)
# IODIR = 0 set pin modes to OUTPUT digit

# mask is kept in ROM
# IO init to 0xff (all read)
# value init to 0