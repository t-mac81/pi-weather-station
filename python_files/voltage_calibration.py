#!/usr/bin/env python3

#import libraries
import busio
import digitalio
import os, sys
import glob
import board
import adafruit_mcp3xxx.mcp3008 as MCP
import time
import RPi.GPIO as GPIO
from adafruit_mcp3xxx.analog_in import AnalogIn
from subprocess import call

#setup MCP3008
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
cs = digitalio.DigitalInOut(board.D5)
mcp = MCP.MCP3008(spi, cs)


#loop to monitor battery voltage
while True:
    time.sleep(1)
    batt_raw = AnalogIn(mcp,MCP.P1) #create battery voltage analog channel on MCP3008 pin 1
    batt_voltage_raw = batt_raw.voltage
    batt_voltage = round(((batt_voltage_raw * 15)/3.3/0.991),1) #scale volatge input: 0-3.3V = 0-15V
    print (batt_voltage)
      
    