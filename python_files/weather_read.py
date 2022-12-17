#!/usr/bin/env python3

#import libraries
import busio
import digitalio
import os
import glob
import board
import adafruit_mcp3xxx.mcp3008 as MCP
import time
import picamera
from picamera import Color
import math
import ftplib
import hashlib
import datetime
import http.client
import subprocess
from statistics import mean
import RPi.GPIO as GPIO
from adafruit_mcp3xxx.analog_in import AnalogIn

#setup MCP3008
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
cs = digitalio.DigitalInOut(board.D5)
mcp = MCP.MCP3008(spi, cs)

#setup inputs for wind speed, direction, and battery voltage
wind_dir_raw= AnalogIn(mcp,MCP.P0) #create wind direction analog channel on MCP3008 pin 0
batt_raw = AnalogIn(mcp,MCP.P1) #create battery voltage analog channel on MCP3008 pin 1 for webcam text
windtick = 0 #used to count the number of times the wind speed input is triggered (GPIO21)
GPIO.setmode(GPIO.BCM) #Set GPIO pins to use BCM pin numbers
GPIO.setup(21,GPIO.IN, pull_up_down=GPIO.PUD_UP) #Setup GPIO21 to an input and enable the pullup

#setup temperature probe input and read temperature in degrees C
os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')
base_dir = '/sys/bus/w1/devices/'
device_folder = glob.glob(base_dir + '28*')[0]
device_file = device_folder + '/w1_slave'

def read_temp_raw():
    catdata = subprocess.Popen(['cat',device_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out,err = catdata.communicate()
    out_decode = out.decode('utf-8')
    lines = out_decode.split('\n')
    return lines

def read_temp():
    lines = read_temp_raw()
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = read_temp_raw()
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        return temp_c

#event to detect wind ticks
GPIO.add_event_detect(21, edge=GPIO.FALLING, bouncetime=30)
def windtrig(self):
    global windtick
    windtick +=1
GPIO.add_event_callback(21,windtrig)

#create lists to store wind speed and direction readings
store_windspeed = []
wind_dir_sin = []
wind_dir_cos = []

#create loop to collect and log wind speed, direction and temperature
interval = 3 #sample period for wind speed and direction in seconds

for i in range(1, 264): #run collection loop 264 times = 13.75 minutes
    time.sleep(interval) #set collection loop duration

    wind_dir_scaled = ((wind_dir_raw.value*360)/65472) #scale the wind direction
    wind_dir_rounded = (wind_dir_scaled) #and round it to one decimal place
    windspeed_mph = windtick * (2.25 / interval) #Calculate windspeed in mph
    windspeed_kts = (windspeed_mph * 0.868976) #convert windspeed to kts (windguru take knots)
    
    #append lists for data loging
    wind_dir_sin.append (math.sin(math.radians(wind_dir_rounded)))
    wind_dir_cos.append (math.cos(math.radians(wind_dir_rounded)))
    store_windspeed.append (windspeed_kts)
    #store_temp.append (temp)
    #print('wind direction: ', wind_dir_rounded ,'degrees')
    #print('wind speed: ', windspeed_kts, 'kts')
    #print('temperature: ', temp, 'degrees C')
    windtick = 0
wind_dir_avg_rad = math.atan2(mean(wind_dir_sin), mean(wind_dir_cos)) #calculation for the vector mean of wind direction in radians
wind_dir_avg = round((math.degrees(wind_dir_avg_rad))) #convert above output to degrees in +180 to -180 format

#if function to convert negative average wind direction
if wind_dir_avg < 0:
    wind_dir_avg_pos = wind_dir_avg + 360
if wind_dir_avg >= 0:
    wind_dir_avg_pos = wind_dir_avg

#Calculate min, max and average wind speeds, temperature and battery voltage
wind_speed_min = round(min(store_windspeed),1)
wind_speed_max = round(max(store_windspeed),1)
wind_speed_avg = round(mean(store_windspeed),1)
temperature = round(read_temp(),1)
batt_voltage_raw = batt_raw.voltage #scale volatge input to 0-3.3V=0-15V
batt_voltage = round(((batt_voltage_raw * 15)/3.3/0.991),1)

#setup variables for upload to windguru
date_time = datetime.datetime.now().strftime('%Y%m%d%H%M')
salt = date_time #use time string in YYYYMMDDHHMM format with time in 24 hour clock
uid = 'flyhills_launch' #weather station unit ID on wind guru
station_password = 'sportbiker6'
#url = '82.208.41.65'
url = 'www.windguru.cz'

#create md5 hash string and upload string for weather data
hash_string = salt +uid +station_password
hash_string_md5 = hashlib.md5(hash_string.encode())
hash_string_md5_hex = hash_string_md5.hexdigest() #hex md5 string for windguru upload
upload_string = '/upload/api.php?uid=' +str(uid) +'&salt=' +str(salt) +'&hash=' +str(hash_string_md5_hex) \
                +'&wind_avg=' +str(wind_speed_avg) +'&wind_min=' +str(wind_speed_min) +'&wind_max=' \
                +str(wind_speed_max) +'&wind_direction=' +str(wind_dir_avg_pos) +'&temperature=' +str(temperature) # need to add measurement interval


#take picture with webcam and add date, time and battery voltage
cam_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
cam_text = (cam_date +' Batt:' +str(batt_voltage) +'V')

with picamera.PiCamera() as camera:
    camera.resolution = (640,480)
    camera.rotation = 0
    camera.annotate_text_size = 15
    camera.annotate_background = Color('black')
    camera.annotate_text = (cam_text)
    #picam warmup time
    time.sleep(2)
    camera.capture('/var/log/weather_pic/picture.jpg', quality = 6) 

print ('average wind direction: ', wind_dir_avg_pos, 'degrees')
print ('minimum wind speed: ', wind_speed_min, 'kts')
print ('maximum wind speed: ', wind_speed_max, 'kts')
print ('average wind speed: ', wind_speed_avg, 'kts')
print ('average temperature: ', temperature, 'degrees C')
#print ('battery voltage: ' , batt_voltage, 'V')
#print (url +upload_string)
print (cam_text)

#Establish PPP session with hologram NOVA
connect_tries = 2
while connect_tries > 0:
    modem_con = subprocess.check_output(['sudo', 'hologram', 'network', 'connect']).decode('utf-8')
    print (modem_con.strip())
    if modem_con.strip() == 'PPP session started':
        print ('modem connection sucessful')
        break
    connect_tries = connect_tries-1
    print ('modem connection failed', connect_tries, 'attempts(s) left')
    time.sleep(4)
    if connect_tries == 1:
        print ('modem connection failed, resetting R410M modem')
        modem_reset = subprocess.check_output(['sudo', 'hologram', 'modem', 'reset']).decode('utf-8')
        print (modem_reset.strip())
        time.sleep(4)
time.sleep(3)

#upload 15 min data to windguru with HTTP GET request
http_tries = 5
for try_http in range(0,http_tries):
    try:
        conn = http.client.HTTPConnection(url)
        conn.request("GET", upload_string)
        r1 = conn.getresponse()    
    except (OSError, http.client.HTTPException):
        print('HTTP GET request failed, %d tries left' % (http_tries - try_http - 1))
        time.sleep(2)        
    else:
        print('HTTP SUCCESS')
        break
try:
    print (r1.status, r1.reason)
except NameError:
    print ('http upload failed')
time.sleep(2)

#FTP picture to webcam site with exception handling
server = 'ftp.webcam.io'
username = 'user_p43wd943'
password = 'CKQODV6mN'
ftp_tries = 5
for try_ftp in range(0,ftp_tries):
    try:
        ftp_connection = ftplib.FTP(server , username , password)
        file = open('/var/log/weather_pic/picture.jpg', 'rb')
        ftp_connection.storbinary('STOR picture1.jpg', file)
        ftp_connection.quit()
        file.close()
    except ftplib.all_errors:
        print('FTP upload failed, %d attempt(s) left' % (ftp_tries - try_ftp - 1))
        time.sleep(2)
    else:
        print('FTP SUCCESS')
        break

#Disconnect hologram NOVA from network
time.sleep(3)
modem_disc = subprocess.check_output(['sudo', 'hologram', 'network', 'disconnect']).decode('utf-8')
print (modem_disc.strip())
end_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
print ('run complete', end_time)

#shutdown if battery voltage below 11.8V
if batt_voltage <= 11.7:
    print (batt_voltage)
    print ('Low Battery Shutdown')
    call("sudo shutdown -h now", shell=True)
        
print (' ')
