import time
import lights

clock = lights.clock(pin=2, frequency=500)
clock.start()

try:
    for i in range(10):
        print(f"Main loop iteration {i}")
        time.sleep(1)  # Main program continues to run
finally:
    clock.stop()  # Stop the clock cleanly