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

logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('port', help='COMx for windows, /dev/ttyUSBx for linux, /dev/tty.usbmodemxxx for mac')
    parser.add_argument('channel')
    return parser.parse_args()

ENTER = '\r'

class GPIO:

    def read(self):
        lines = []
        line = None
        # skip empty lines
        while not line:
            line = self.port.readline()
        # read all non-empty lines
        while line:
            logger.debug(f'read: {line}')
            lines.append(line)
            line = self.port.readline()
        # lines[-3] is the command itself
        # lines[-2] is the result, begin with '\r' and end with '\n'
        # lines[-1] is the prompt
        assert len(lines) >= 3
        assert lines[-2].startswith(b'\r'), lines[-2]
        assert lines[-2].endswith(b'\n'), lines[-2]
        return lines[-2][1:-1]

    def consume(self):
        lines = []
        line = None
        while not line:
            line = self.port.readline()
        while line:
            logger.debug(f'read: {line}')
            lines.append(line)
            line = self.port.readline()
        # lines[-2] is the command itself
        # lines[-1] is the prompt

    def write(self, s):
        self.port.write(f'{s}{ENTER}'.encode())

    def __init__(self, port_file):
        self.port = serial.Serial(port_file, 19200, timeout=0)

    def close(self):
        self.port.close()

    @property
    def int(self):
        return self.gpio_readall()
    
    @int.setter
    def int(self, value):
        self.gpio_writeall(value)

    def gpio_writeall(self, value):
        self.write(f'gpio writeall {value:02x}')
        self.consume()
    
    def gpio_readall(self):
        self.write('gpio readall')
        return int(self.read(), 16)

    @property
    def version(self):
        self.write('ver')
        line = self.read()
        return line.decode()

    def gpio_read(self, channel):
        self.write(f'gpio read {channel}')
        line = self.read()
        return int(line)

    def gpio_write(self, channel, b):
        cmd = ['clear', 'set'][bool(b)]
        self.write(f'gpio {cmd} {channel}')
        self.consume()

    def adc_read(self, channel):
        self.write(f'adc read {channel}')
        line = self.read()
        return int(line)

    def mask(self, value):
        '''
        affect writeall/iodir
        0 to mask out
        1 to allow operations
        '''
        self.write(f'gpio iomask {value:02x}')
        self.consume()
    
    def iodir(self, value):
        '''
        0 for output, 1 for input
        can be overwirtten by subsequent set/clear/read/adc command
        '''
        self.write(f'gpio iodir {value:02x}')
        self.consume()

    @property
    def id(self, value=0):
        self.write('id get')
        return self.read().decode()

    @id.setter
    def id(self, value=0):
        if type(value) == int: value = f'{value:08}'
        value = str(value)[:8]
        self.write(f'id set {value:>8}')
        self.consume()

    def __repr__(self):
        return f'<gpio version: {self.version}; id: {self.id}; int: {self.int}>'

@pytest.fixture
def gpio():
    global goio
    gpio = GPIO('COM4')
    gpio.int = 0
    gpio.gpio_write(0, 0)
    return gpio

def test_id(gpio):
    gpio.id = '0123456789abcdef'
    assert gpio.id == '01234567'
    gpio.id = 0x123
    assert gpio.id == '00000291'
    gpio.id = 0
    assert gpio.id == '00000000'

def test_version(gpio):
    assert gpio.version == '00000008'

def test_int(gpio):
    assert 0 == gpio.int
    gpio.int = 0xff
    assert 0xff == gpio.int
    gpio.int = 0

def main(port, channel):
    gpio = GPIO(port)
    gpio.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    args = parse_args()
    main(args.port, args.channel)
