from machine import Pin
import utime

# -------- CONFIG --------
clock_pin_number = 2   # GPIO used for clock input
output_pins_numbers = [
    3,4,5,6,7,8,9,10,11,12,
    13,14,15,16,17,18,19,20,21,22
]  # 20 output pins
# ------------------------

# Setup clock input (with pull-down resistor)
clock = Pin(clock_pin_number, Pin.IN, Pin.PULL_DOWN)

# Setup output pins
outputs = []
for pin_num in output_pins_numbers:
    p = Pin(pin_num, Pin.OUT)
    p.value(0)
    outputs.append(p)

current_index = 0

# Turn on first pin initially
outputs[current_index].value(1)

last_clock_state = 0

while True:
    current_clock_state = clock.value()

    # Detect rising edge
    if current_clock_state == 1 and last_clock_state == 0:
        
        # Turn off current pin
        outputs[current_index].value(0)

        # Move to next pin
        current_index += 1
        if current_index >= len(outputs):
            current_index = 0

        # Turn on next pin
        outputs[current_index].value(1)

        # Small debounce delay
        utime.sleep_ms(5)

    last_clock_state = current_clock_state