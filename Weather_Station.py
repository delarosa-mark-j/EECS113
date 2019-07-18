'''
    Group 24 EECS 113 Weather Station
    Sean Santarsiero #53061926
    Mark Delarosa    #46499661
    Sean Kerr        #45774632
'''

# Firmware Imports
import RPi.GPIO as GPIO
import time
import Freenove_DHT as DHT
import I2C_LCD_driver
import time, threading
from datetime import datetime

# Selenium Imports
import csv
import os
import sys
from datetime import date
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys

#GPIO PIN INIT
GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

#PIN ALLOCATION
mylcd = I2C_LCD_driver.lcd()
DHTPin = 7 #define the pin of DHT11
dht = DHT.DHT(DHTPin) #create a DHT class object
sensorPin = 11
WaterRelay = 37

#I/O Setup
GPIO.setup(WaterRelay, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(sensorPin, GPIO.IN)

'''
    START
    Global Variables and Dictionaries
'''
global sumCnt
sumCnt = 0 

#avgDHT Dictionary
global AVG_DHT
AVG_DHT = {'sumT': 0.0, 'sumH': 0.0, 'avgT': 0.0, 'avgH': 0.0, 'eto': 0.000}

#Weather Station Dictionary
global CIMIS
CIMIS = {'eto': 0.01, 'temp': 0.0, 'hum': 52.1}

#local Station Dictionary
global LOCAL 
LOCAL = {'eto': 0.0, 'temp': 0.0, 'hum': 0.0}

#sensor
global IRsensorFlag
IRsensorFlag = 0;

#waterRelay for get water
global startWateringKey
startWateringKey = 0

'''
    END
    Global Variables and Dictionaries
'''

def getDHT():
    
    global sumCnt
    global LOCAL
    global AVG_DHT

    t = threading.Timer(60, getDHT).start()
    chk = dht.readDHT11() #read DHT11 and get a return value. Then determine

    #check if we received bad values from the DHT sensor and dont except them
    while(((dht.humidity < 0) and (dht.temperature < 0)) or (dht.humidity > 100)):
        chk = dht.readDHT11()
        
    LOCAL['temp'] = dht.temperature
    LOCAL['hum']  = dht.humidity 
    
    sumCnt  += 1 #counting number of reading times
    AVG_DHT['sumT']  += LOCAL['temp']
    AVG_DHT['sumH']  += LOCAL['hum']
    print(time.ctime())
    print ("The sumCnt is : %d, \t chk : %d"% (sumCnt,chk))
    print("Humidity : %.2f, \t Temperature : %.2f \n"% (dht.humidity,dht.temperature))
    
    
# LCD Function that cycles through 4 States to display data    
def print2lcd(LCD_state):
    global LOCAL
    global CIMIS
    global AVG_DHT
    global IRsensorFlag

    state = 1
    
    if(not IRsensorFlag):
        #Display DHT
        if(LCD_state == 1):
            mylcd.lcd_display_string("(1) Hum: %.2f "% (LOCAL['hum']), 1)
            mylcd.lcd_display_string("    Temp: %.2f "% (LOCAL['temp']), 2)
            state = 2
        #Display CIMIS
        elif(LCD_state == 2):
            mylcd.lcd_display_string("(2) Hum: %.2f "% (CIMIS['hum']), 1)
            mylcd.lcd_display_string("    Temp: %.2f "% (tempConv(CIMIS['temp'])), 2)
            state = 3
        #Display ETO
        elif(LCD_state == 3):
            mylcd.lcd_display_string("(3)ET(L): %.3f "% (AVG_DHT['eto']), 1)
            mylcd.lcd_display_string("   ET(S): %.3f "% (CIMIS['eto']), 2)
            state = 4
        #Display Watering Plan
        elif(LCD_state == 4):
            mylcd.lcd_display_string("                ", 1)
            mylcd.lcd_display_string("                ", 2)
            hum_factor = AVG_DHT['avgH']/CIMIS['hum']
            mylcd.lcd_display_string("(4)HF: %.2f "% (hum_factor), 1)
            if(hum_factor >= 1):
                mylcd.lcd_display_string("   Water Less", 2)
            else:
                mylcd.lcd_display_string("   Water More", 2)
            state = 1
        
    threading.Timer(5,print2lcd, [state,]).start()

# calculate the humidity factor and average DHT values
def getETO():
    global AVG_DHT
    global CIMIS
    
    if(AVG_DHT['avgH'] > 0.0):
        print("avgH inside: " + str(AVG_DHT['avgH']))
        hum_factor = AVG_DHT['avgH']/CIMIS['hum']
        AVG_DHT['eto'] = CIMIS['eto'] / hum_factor
        print ("ETO: " + str(AVG_DHT['eto']))
    
    threading.Timer(60,getETO).start()
    
def getWater():
    global CIMI
    global debtWait
    
    start = time.time() # record start time of function
    
    #init variables for calculations
    PF = 1.0
    SF = 1500.0
    IE = .80
    
    WaterPD = (CIMIS['eto'] * PF * SF * .62)/IE
    WaterDebt = WaterPD/1020.0 #divide by 1020 to water hourly
    WaterDebt = WaterDebt*3600 #convert hours to seconds
    
    while(1):
        #if motion detected, pause watering, print to lcd and wait
        if(GPIO.input(sensorPin) == GPIO.HIGH):
            GPIO.output(WaterRelay, GPIO.LOW)
            mylcd.lcd_display_string("motion          ", 1)
            mylcd.lcd_display_string("detected        ", 2)
            time.sleep(2)
            print("MOTION DETECTED")
            time.sleep(30)
            
        # else keep watering and  
        GPIO.output(WaterRelay, GPIO.HIGH)
        print("water debt %.2f" % WaterDebt)
        time.sleep(1)
        WaterDebt = WaterDebt - 1 #decrement the time needed to water
        
        #leave while loop if time watering is up
        if(WaterDebt<=0):
            break
   
    GPIO.output(WaterRelay, GPIO.LOW) # turn of water
    
    #because of sleeps above this formula give true thread timing amount
    end = time.time()
    trueHour = 3600 - (end - start)
    
    threading.Timer(trueHour,getWater).start()
    
'''
    START
    Python Web Crawl Script
'''

#Function to clear line of text
def clear_line(element):
    for x in range(0,9,1):
        element.send_keys(Keys.BACKSPACE)

#function to automate login
def login(driver):

    username = driver.find_element_by_id('MainContent_txtUserName')
    username.send_keys('ssantars@uci.edu')

    password = driver.find_element_by_id('MainContent_txtPassword')
    password.send_keys('Group24')

    complete_login = driver.find_element_by_id('MainContent_btnLogin')
    complete_login.click()

#function to fill in report protocol for Irvine Station w/ Current date and Hourly CSV File
def prompt_Report(driver):
    data_tab = driver.find_element_by_id('lnkData')
    data_tab.click()

    time.sleep(1)

    station_table = driver.find_element_by_id('divStationsForReport')
    irvine_station = station_table.find_element_by_xpath("//tr//td[contains(text(), 'Irvine')]")
    irvine_station.click()

    report_type = driver.find_element_by_id('ctl00_MainContent_cbBasicReportType_Input')
    report_type.send_keys("a Hourly")
    report_type.submit()

    time.sleep(2)
    report = driver.find_element_by_id('ctl00_MainContent_cbOutputMethod_Input')
    report.send_keys('CSV')

    d = date.today().strftime('%m/%d/%Y')
    date_type = driver.find_element_by_id('ctl00_MainContent_dpHourlyStart_dateInput')
    clear_line(date_type)
    date_type.send_keys(d)

    submit = driver.find_element_by_id('MainContent_btnSubmit')
    submit.click()

    time.sleep(1)
    driver.close()

#Extract CSN data from CSV generated from CIMIS
def getCIMIS():
    global CIMIS
    
    driver = webdriver.Chrome("/usr/lib/chromium-browser/chromedriver")
    driver.get("https://cimis.water.ca.gov/Auth/Login.aspx")


    login(driver)
    prompt_Report(driver)

    f = open(r'/home/pi/Downloads/hourly.csv',"r")
    csv_file = csv.reader(f, delimiter=",")
    currentTime = datetime.now().strftime("%H00")
    prevHour = int(currentTime) - 100
    print ("Prevhour: " + str(prevHour))
    for row in csv_file:
        try:

            if (row[4] == str(prevHour)):
                print("Webcrawl Values\n eto: " + str(row[6]) + " hum: " + str(row[16]) + " temp: " + str(row[14]))
                CIMIS['eto']  = float(row[6])
                CIMIS['hum']  = float(row[16])
                CIMIS['temp'] = float(row[14])
                
                
        except:
            print ("Exception")
            CIMIS['eto']  = 0.01
            CIMIS['hum']  = CIMIS['hum']
            CIMIS['temp'] = CIMIS['temp']
            

    f.close()
        
    os.remove(r'/home/pi/Downloads/hourly.csv')
    threading.Timer(3600,getCIMIS).start()

'''
    END
    Python Web Crawl Script
'''

def tempConv(f_temp):

    c_temp = (f_temp - 32) *(5/9)

    return c_temp    
    
def avgDHT():
    global sumCnt
    global avgDHT
    global startWateringKey
    counter = time.ctime()

    #enter every hour and calculate average DHT values
    if(sumCnt >= 60):
        print("The time is " + str(counter))
        AVG_DHT['avgT'] = AVG_DHT['sumT']/sumCnt
        AVG_DHT['avgH'] = AVG_DHT['sumH']/sumCnt
        print("avgT" + str(AVG_DHT['avgT']))
        print("avgT" + str(AVG_DHT['avgT']))
        sumCnt = 0
        AVG_DHT['sumT'] = 0
        AVG_DHT['sumH'] = 0
        
        #getWater is called only once, the time time it enters above if statement
        if(startWateringKey == 0):
            startWateringKey = 1
            getWater()

    threading.Timer(60,avgDHT).start()

    
'''
    Python Web 
'''

#call and init processes

getCIMIS()
getDHT()
print2lcd(1)
getETO()
avgDHT()


#________MAIN__________

while(1):
    
    try:
        time.sleep(1)
    
    except KeyboardInterrupt:
        GPIO.cleanup()
        exit()
    



