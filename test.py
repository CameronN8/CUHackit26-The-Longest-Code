import time
import lights

# Create a clock on GPIO 17 with 2 Hz
clock = lights.clock(pin=17, frequency=500)
clock.start()  # Starts clock in background

try:
    for i in range(10):
        print(f"Main loop iteration {i}")
        time.sleep(1)  # Main program continues to run
finally:
    clock.stop()  # Stop the clock cleanly