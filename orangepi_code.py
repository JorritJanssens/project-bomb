import wiringpi
import time
import random
import paho.mqtt.client as mqtt
import threading
import cv2
import cvzone
import random
from cvzone.HandTrackingModule import HandDetector
from ClassLCD import LCD

# Hier geef ik alle nodige MQTT settings die hij nodig heeft.
MQTT_HOST = "mqtt3.thingspeak.com"
MQTT_PORT = 1883
MQTT_KEEPALIVE_INTERVAL = 60
MQTT_TOPIC_PUBLISH = "channels/2559406/publish"
MQTT_TOPIC_SUBSCRIBE_field1 = "channels/2559406/subscribe/fields/field1"
MQTT_TOPIC_SUBSCRIBE_field2 = "channels/2559406/subscribe/fields/field2"
MQTT_TOPIC_SUBSCRIBE_field3 = "channels/2559406/subscribe/fields/field3"
MQTT_CLIENT_ID = "YOURCLIENTID"
MQTT_USER = "YOURUSER"
MQTT_PWD = "YOURPASSWORD"

# Variabelen om de ontvangen waarden op te slaan
field1_value = None
field2_value = None
field3_value = None
keepGoing = True
finishTimer_lock = threading.Lock()
keepGoing_lock = threading.Lock()
stateBomb_lock = threading.Lock()
instructionUser_lock = threading.Lock()
finishTimer = False

def start_countdown(duration):
    global finishTimer

    stop_timer = False  # Flag to indicate whether the timer should stop

    def countdown_timer(duration):
        nonlocal stop_timer  # Use nonlocal to access the outer scope variable
        print("Starting countdown timer...")
        while duration >= 0 and not stop_timer:  # Ensure the timer stops when duration reaches 0 or stop_timer is True
            mins, secs = divmod(duration, 60)
            timer_display = f"{mins:02d}:{secs:02d}"
            print(timer_display, end='\r')
            setTimeLeft("Boom in: " + timer_display)
            time.sleep(1)
            if(duration >= 0):
                duration -= 1
            if(finishTimer):
                print("Congratsulations! You survived!\n")
                print("Your time is: " + timer_display, end='\n')
                stop_timer = True  # Set the flag to stop the timer
                display_string_on_lcd(f'Great job! You survived!')
                time.sleep(5)
                ActivateLCD()
                turnOffLCD()
            while duration == -1:
                if(not isBlinking):
                    updateKeepGoing(False)
                    print("You blew up. Better luck next time!")
                    print("Time remaining: " + timer_display, end='\n')
                    display_string_on_lcd(f'You blew up. Better luck next time!')
                    time.sleep(5)
                    turnOffLCD()
                    reset_progress()
                    stop_timer = True  # Set the flag to stop the timer
                    duration = 0 
            if(stop_timer):
                turnModuleLightsOff()      
                publishLatestTime(f'{mins:02d}.{secs:02d}')    
    countdown_thread = threading.Thread(target=countdown_timer, args=(duration,))
    countdown_thread.start()

# MQTT client initialization
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1 ,MQTT_CLIENT_ID)
mqtt_client.username_pw_set(MQTT_USER, MQTT_PWD)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected OK with result code " + str(rc))
        # Abonneer op de subscribe-topics voor elk veld
        client.subscribe(MQTT_TOPIC_SUBSCRIBE_field1)
        client.subscribe(MQTT_TOPIC_SUBSCRIBE_field2)
        client.subscribe(MQTT_TOPIC_SUBSCRIBE_field3)
        time.sleep(5)
    else:
        print("Bad connection with result code " + str(rc))

def on_disconnect(client, userdata, flags, rc=0):
    print("Disconnected result code " + str(rc))

def on_message(client, userdata, msg):
    global field1_value, field2_value, field3_value
    print("Received a message on topic: " + msg.topic + "; message: " + msg.payload.decode())
    # Opslaan van de ontvangen waarde in de juiste variabele op basis van het topic
    if msg.topic == MQTT_TOPIC_SUBSCRIBE_field1:
        field1_value = float(msg.payload.decode())
    elif msg.topic == MQTT_TOPIC_SUBSCRIBE_field2:
        field2_value = float(msg.payload.decode())
    elif msg.topic == MQTT_TOPIC_SUBSCRIBE_field3:
        field3_value = float(msg.payload.decode())


# Connect callback handlers to client
mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message

mqtt_client.connect(MQTT_HOST, MQTT_PORT)
mqtt_client.loop_start()# de MQTT client op starten

def publish_score(safeScore):
    print("In publish method \n")
    MQTT_DATA = "field3=" + str(safeScore) + "&status=MQTTPUBLISH"
    print("MQTT data: " + MQTT_DATA + "\n")
    try:
        print("Publishing now..\n")
        mqtt_client.publish(topic=MQTT_TOPIC_PUBLISH, payload=MQTT_DATA, qos=0, retain=False, properties=None)
    except OSError:
        print("Got error\n")
        mqtt_client.reconnect()

def ActivateADC():
    wiringpi.digitalWrite(pin_CS_adc, 0) # Actived ADC using CS
    time.sleep(0.000005)

def DeactivateADC():
    wiringpi.digitalWrite(pin_CS_adc, 1) # Deactived ADC using CS
    time.sleep(0.000005)

def readadc(adcnum):
    if ((adcnum > 7) or (adcnum < 0)):
        return -1
    revlen, recvData = wiringpi.wiringPiSPIDataRW(1, bytes([1,(8+adcnum)<<4,0]))
    time.sleep(0.000005)
    adcout = ((recvData[1]&3) << 8) + recvData[2]
    return adcout

def isSolved(number, target, range):
    return abs(number - target) <= range

def generateRandomNumber(tmp0):
    generatedNumber = random.randint(0,973)
    while(isSolved(tmp0, generatedNumber, rangeToNotBeForSolution)):
        generatedNumber = random.randint(0,973)
    return generatedNumber

def calculate_percentage(current_value, target_number):
    if current_value <= 0:
        return 0  # Handle edge case when the current value is zero or negative
    elif current_value > target_number:
        excess_value = current_value - target_number
        # print(f"Percentage progress: {int(max(0, 100 - (excess_value / target_number) * 100))}%")
        return int(max(0, 100 - (excess_value / target_number) * 100))
    else:
        # print(f"Percentage progress: {int(min(100, (current_value / target_number) * 100))}%")
        return int(min(100, (current_value / target_number) * 100))
####Stepper Motor#####
def spin_motor(steps):
    print("Spinning motor...")
    for _ in range(steps):
        wiringpi.digitalWrite(coil_A_1_pin, 0)
        wiringpi.digitalWrite(coil_A_2_pin, 1)
        wiringpi.digitalWrite(coil_B_1_pin, 1)
        wiringpi.digitalWrite(coil_B_2_pin, 0)
        time.sleep(0.01)  # Delay 10 milliseconds
        wiringpi.digitalWrite(coil_A_1_pin, 0)
        wiringpi.digitalWrite(coil_A_2_pin, 0)
        wiringpi.digitalWrite(coil_B_1_pin, 1)
        wiringpi.digitalWrite(coil_B_2_pin, 1)
        time.sleep(0.01)  # Delay 10 milliseconds
        wiringpi.digitalWrite(coil_A_1_pin, 1)
        wiringpi.digitalWrite(coil_A_2_pin, 0)
        wiringpi.digitalWrite(coil_B_1_pin, 0)
        wiringpi.digitalWrite(coil_B_2_pin, 1)
        time.sleep(0.01)  # Delay 10 milliseconds
        wiringpi.digitalWrite(coil_A_1_pin, 1)
        wiringpi.digitalWrite(coil_A_2_pin, 1)
        wiringpi.digitalWrite(coil_B_1_pin, 0)
        wiringpi.digitalWrite(coil_B_2_pin, 0)
        time.sleep(0.01)  # Delay 10 milliseconds
        wiringpi.digitalWrite(coil_A_1_pin, 0)
        wiringpi.digitalWrite(coil_A_2_pin, 1)
        wiringpi.digitalWrite(coil_B_1_pin, 1)
        wiringpi.digitalWrite(coil_B_2_pin, 0)
        time.sleep(0.01)  # Delay 10 milliseconds
        wiringpi.digitalWrite(coil_A_1_pin, 0)
        wiringpi.digitalWrite(coil_A_2_pin, 0)
        wiringpi.digitalWrite(coil_B_1_pin, 1)
        wiringpi.digitalWrite(coil_B_2_pin, 1)
        time.sleep(0.01)  # Delay 10 milliseconds
        wiringpi.digitalWrite(coil_A_1_pin, 1)
        wiringpi.digitalWrite(coil_A_2_pin, 0)
        wiringpi.digitalWrite(coil_B_1_pin, 0)
        wiringpi.digitalWrite(coil_B_2_pin, 1)
        time.sleep(0.01)  # Delay 10 milliseconds
        wiringpi.digitalWrite(coil_A_1_pin, 1)
        wiringpi.digitalWrite(coil_A_2_pin, 0)
        wiringpi.digitalWrite(coil_B_1_pin, 0)
        wiringpi.digitalWrite(coil_B_2_pin, 1)
        time.sleep(0.01)  # Delay 10 milliseconds
    wiringpi.digitalWrite(coil_A_1_pin, 0)
    wiringpi.digitalWrite(coil_A_2_pin, 0)
    wiringpi.digitalWrite(coil_B_1_pin, 0)
    wiringpi.digitalWrite(coil_B_2_pin, 0)        

####Handdetector code#####
# Function to initialize the camera
def initialize_camera():
    cap = cv2.VideoCapture(1)
    return cap

# Function to initialize hand detector
def initialize_detector(detection_con=0.5, max_hands=1):
    detector = HandDetector(detectionCon=detection_con, maxHands=max_hands)
    return detector

# Function to process frame and detect hands
def process_frame(cap, detector):
    success, img = cap.read()
    if not success:
        return None, None

    img = cv2.resize(img, (500, 350))
    hands, img = detector.findHands(img)
    return img, hands

# Function to count raised fingers
def count_raised_fingers(hands, detector):
    if hands:
        hand = hands[0]
        fingers = detector.fingersUp(hand)
        return sum(fingers)
    return 0

# Function to generate a random code of digits between 1-5 with a given length
def generate_code(length):
    if length <= 0:
        return []

    hands = ["Left", "Right"]
    code = [(random.choice(hands), random.randint(1, 5))]

    while len(code) < length:
        #Get random hand
        next_hand = random.choice(hands)
        # Get random amount of fingers
        next_digit = random.randint(1, 5)
        #If the same hand and amount of fingers are generated, generate a new one
        while next_hand == code[-1][0] and next_digit == code[-1][1]:
            next_hand = random.choice(hands)
            next_digit = random.randint(1, 5)
        # Add it to the generated code
        code.append((next_hand, next_digit))
    
    return code

def display_string_on_lcd(string):
    DeactivateLCD()
    lcd_1.set_backlight(1)  # Turn on the backlight
    ActivateLCD()
    lcd_1.clear()
    lcd_1.go_to_xy(0, 0)
    lcd_1.put_string(f'{getTimeLeft()}\n{string}')
    lcd_1.refresh()


###Morsecode###
def blinkShort(_pin):
    wiringpi.softPwmWrite(_pin,100)
    time.sleep(0.5)
    wiringpi.softPwmWrite(_pin,0)
    time.sleep(0.5)

def blinkLong(_pin):
    wiringpi.softPwmWrite(_pin,100)
    time.sleep(1)
    wiringpi.softPwmWrite(_pin,0)
    time.sleep(0.5)

def switch_numbers(number):
    numbers = {
        1: ['short', 'long', 'long', 'long', 'long'],
        2: ['short', 'short', 'long', 'long', 'long'],
        3: ['short', 'short', 'short', 'long', 'long'],
        4: ['short', 'short', 'short', 'short', 'long'],
        5: ['short', 'short', 'short', 'short', 'short'],
        6: ['long', 'short', 'short', 'short', 'short'],
        7: ['long', 'long', 'short', 'short', 'short'],
        8: ['long', 'long', 'long', 'short', 'short'],
        9: ['long', 'long', 'long', 'long', 'short'],
        0: ['long', 'long', 'long', 'long', 'long'],
    }
    return numbers.get(number, "No number")

def setIsBlinking(newValue):
    global isBlinking
    isBlinking = newValue

def blink(code):
    setIsBlinking(True)
    for digit in code:
        sequence = switch_numbers(int(digit))
        # print(sequence)
        # print("\n")
        for signal in sequence:
            # print(signal + "\n")
            if signal == 'short':
                blinkShort(pinMorseSafeLight)
            else:
                blinkLong(pinMorseSafeLight)

        time.sleep(2)
    setIsBlinking(False)
    if(getTimeLeft() == "00:00"):
        updateKeepGoing(False)

def turnOffLCD():
   lcd_1.clear()
   lcd_1.refresh()
   lcd_1.set_backlight(0)
   DeactivateLCD()

def ActivateLCD():
    wiringpi.digitalWrite(pin_CS_lcd, 0)       # Actived LCD using CS
    time.sleep(0.000005)

def DeactivateLCD():
    wiringpi.digitalWrite(pin_CS_lcd, 1)       # Deactived LCD using CS
    time.sleep(0.000005)

def generateMorseCode():
    code = str(random.randint(0, 9))
    while len(code) < 4:
        next_digit = random.randint(0, 9)
        if next_digit != int(code[-1]):
            code += str(next_digit)
    return code

debounce_time = 0.2  # 200 milliseconds debounce time

def debounce_read(pin):
    state = wiringpi.digitalRead(pin)
    time.sleep(debounce_time)
    return state == wiringpi.digitalRead(pin)

####miscellanous####
def turnModuleLightsOff():
    wiringpi.softPwmWrite(pinMorseSafeLight, 0)   
def publishLatestTime(latestTime):
    if(latestTime == "00.00"):
        latestTime = "0"
    MQTT_DATA = "field1=" + latestTime + "&status=MQTTPUBLISH"
    print("MQTT data: " + MQTT_DATA + "\n")
    try:
        print("Publishing now..\n")
        mqtt_client.publish(topic=MQTT_TOPIC_PUBLISH, payload=MQTT_DATA, qos=0, retain=False, properties=None)
        time.sleep(15)
    except OSError:
        print("Got error\n")
        mqtt_client.reconnect()

def getTimeLeft():
    global instructionUser
    return instructionUser

def setTimeLeft(timeLeft):
    global instructionUser
    instructionUser = timeLeft

def updateKeepGoing(value):
    global keepGoing
    keepGoing = value
    print(f'Keep Going now set to: {keepGoing}\n')

# Setup
pin_CS_adc = 16 #We will use w16 as CE, not the default pin w15!
wiringpi.wiringPiSetup()
wiringpi.pinMode(pin_CS_adc, 1) # Set ce to mode 1 ( OUTPUT )
wiringpi.wiringPiSPISetupMode(1, 0, 400000, 0) #(channel, port, speed, mode)

PIN_OUT     =   {  
                'SCLK'  :   14,
                'DIN'   :   11,
                'DC'    :   2, 
                'CS'    :   15, #We will not connect this pin! --> we use w13
                'RST'   :   10,
                'LED'   :   7, #backlight   
}

# Define LCD and buttons
pin_CS_lcd = 13
pinSwitch = 0
pinSwitch2 = 1
pinSwitchEnter = 5

# Define GPIO pins (Stepper)
coil_A_1_pin = 3
coil_A_2_pin = 4
coil_B_1_pin = 6
coil_B_2_pin = 9

instructionUser = ""
stepsToReset = 256
isBlinking = False

#Activate the Stepper pins
wiringpi.pinMode(coil_A_1_pin, wiringpi.OUTPUT)
wiringpi.pinMode(coil_A_2_pin, wiringpi.OUTPUT)
wiringpi.pinMode(coil_B_1_pin, wiringpi.OUTPUT)
wiringpi.pinMode(coil_B_2_pin, wiringpi.OUTPUT)

ActivateLCD() #When removed here, the 0000 won't be displayed
lcd_1 = LCD(PIN_OUT)
wiringpi.pinMode(pinSwitch, 0)
wiringpi.pinMode(pinSwitch2, 0)
wiringpi.pinMode(pinSwitchEnter, 0)
wiringpi.pinMode(pin_CS_lcd , 1)            # Set pin to mode 1 ( OUTPUT )
correctNum = "2003" #generateMorseCode()
print(str(correctNum) + "\n")

rangeToNotBeForSolution = 75
rangeToBeWithinToSolveSafe = 10
scoreToReach = 3
pinMorseSafeLight = 8
wiringpi.pinMode(pinMorseSafeLight, 1)
# Setup PWM for pin3
wiringpi.softPwmCreate(pinMorseSafeLight, 0, 100)  # Setup PWM on pin3 with a range from 0 to 100

def update_progress(state_bomb):
    global stepsToReset
    if(state_bomb < 4):
        spin_motor(22) # move progress up
        stepsToReset -= 22
    else:
        spin_motor(190) # reset motor
        stepsToReset -= 190
def reset_progress():
    if(stateBomb != 1):
        global stepsToReset
        spin_motor(stepsToReset)   

def main():
    global finishTimer
    global keepGoing
    global stateBomb
    ActivateADC()
    tmp0 = readadc(0) # read channel 0
    DeactivateADC()
    target_number = generateRandomNumber(tmp0)
    print("The target to fall in, is: " + str(target_number) + " \n")
    safeScore = 0
    # Start the countdown timer in a separate thread
    countdown_duration = 210 # 3 minutes and 30 seconds
    start_countdown(countdown_duration)
    keepGoing = True
    stateBomb = 1
    cap = initialize_camera()
    detector = initialize_detector()
    i1=0
    i2=0
    i3=0
    i4=0
    position = 1
    code_length = 5  # Length of the code FingerDetector
    code = generate_code(code_length)
    try:
        lcd_1.clear()
        lcd_1.set_backlight(1)
        while keepGoing:
            if(stateBomb == 1):
                # print(f'{keepGoing}\n')
                ActivateADC()
                tmp0 = readadc(0) # read channel 0
                DeactivateADC()
                ActivateLCD()
                display_string_on_lcd(f'Solved {str(safeScore)}/{str(scoreToReach)} combinations!')
                # print ("input0:",tmp0)
                wiringpi.softPwmWrite(pinMorseSafeLight, calculate_percentage(tmp0, target_number))
                if(isSolved(tmp0, target_number, rangeToBeWithinToSolveSafe)):
                    safeScore += 1
                    wiringpi.softPwmWrite(pinMorseSafeLight, 0)
                    time.sleep(0.1)
                    wiringpi.softPwmWrite(pinMorseSafeLight, 100)   
                    print("Correct!")
                    display_string_on_lcd(f'Correct!')
                    publish_score(safeScore)  # Update score to MQTT dashboard
                    if(safeScore == scoreToReach):
                        time.sleep(0.1)
                        wiringpi.softPwmWrite(pinMorseSafeLight, 0)
                        update_progress(stateBomb)
                        stateBomb = 2
                        turnOffLCD()
                    else:
                        target_number = generateRandomNumber(tmp0)
                        time.sleep(0.2)
            elif(stateBomb == 2):
                blink(correctNum)
                lcd_1.set_backlight(1)
                while stateBomb == 2 and keepGoing:    
                    ActivateLCD()
                    lcd_1.clear()
                    lcd_1.go_to_xy(0, 0)
                    if(wiringpi.digitalRead(pinSwitch2) == 0):
                        if(position == 4):
                            position = 1
                        else:
                            position += 1
                    else:
                        position += 0
                    time.sleep(0.05)        
                    if(wiringpi.digitalRead(pinSwitch) == 0):
                        display_string_on_lcd(f'{str(i1)}{str(i2)}{str(i3)}{str(i4)}')
                        if(position == 1):
                            if(i1 == 9):
                                i1 = 0
                            else:
                                print("Before: " + str(i1) + "\n")
                                i1 = i1+1
                                print("After: " + str(i1) + "\n")
                        elif(position == 2):
                            if(i2 == 9):
                                i2 = 0
                            else:
                                i2 = i2+1
                        elif(position == 3):
                            if(i3 == 9):
                                i3 = 0
                            else:
                                i3 = i3+1
                        elif(position == 4):
                            if(i4 == 9):
                                i4 = 0
                            else:
                                i4 = i4+1
                        time.sleep(debounce_time)        
                    else:
                        display_string_on_lcd(f'{str(i1)}{str(i2)}{str(i3)}{str(i4)}')
                    
                    if(wiringpi.digitalRead(pinSwitchEnter) == 0):
                        number = str(i1) + str(i2) + str(i3) + str(i4)
                        lcd_1.refresh()
                        if(number == correctNum):   
                            display_string_on_lcd(f'JUIST!')
                            time.sleep(1)
                            turnOffLCD()
                            print(f"Correct! That is the right code!\n")
                            update_progress(stateBomb)
                            stateBomb = 3
                        else:
                            display_string_on_lcd(f'FOUT!')
                            time.sleep(1)
                            turnOffLCD()
                            blink(correctNum)
            elif(stateBomb == 3):
                img, hands = process_frame(cap, detector)
                if code:  # Check if the list is still not empty after popping
                    expected_hand, expected_fingers = code[0]
                    # Display hand and amount of fingers
                    display_string_on_lcd(f"Hold up {expected_fingers} fingers from {expected_hand} hand")              
                if hands:
                    for hand in hands:
                        hand_type = hand['type']  # Get the hand type (left or right)
                        finger_count = count_raised_fingers(hands, detector)
                        #print(f"Hand: {hand_type}, Fingers: {finger_count}")
                        if code and code[0] == (hand_type, finger_count):
                            code.pop(0)  # Remove the first element
                            print(f"Matched and removed {finger_count}. Remaining code: {code}")
                            display_string_on_lcd(f"Well done!")                          
                        if not code:  # If all code digits are matched
                            display_string_on_lcd('DONE!')
                            update_progress(stateBomb)
                            stateBomb = 4
                            time.sleep(1)
            elif(stateBomb == 4):
                display_string_on_lcd(f'Quick! Get number below 5!\nCurrently: {field2_value}')
                if(field2_value == None):
                    pass
                elif(float(field2_value) < 5):
                    keepGoing = False
                    finishTimer = True
                    update_progress(stateBomb)
    except KeyboardInterrupt:
        ActivateLCD()
        turnOffLCD()
        reset_progress()
        turnModuleLightsOff()      
        print("The bomb state was: " + str(stateBomb) + " \n")
        print("\nProgram terminated")
if __name__ == "__main__":
    main()

# Disconnect MQTT client
mqtt_client.loop_stop()
mqtt_client.disconnect()
