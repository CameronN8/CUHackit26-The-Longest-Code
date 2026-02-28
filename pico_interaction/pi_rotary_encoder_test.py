"""Simple Raspberry Pi rotary encoder tester.

Prints:
- current encoder count when it changes
- button pressed/released edges
"""

import time

import RPi.GPIO as GPIO


# BCM pin numbers (change to match your wiring)
ENC_CLK_PIN = 17
ENC_DT_PIN = 27
ENC_SW_PIN = 22

POLL_DELAY_S = 0.002
BUTTON_DEBOUNCE_S = 0.05


def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(ENC_CLK_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(ENC_DT_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(ENC_SW_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    last_clk = GPIO.input(ENC_CLK_PIN)
    last_btn = GPIO.input(ENC_SW_PIN)
    last_btn_time = 0.0
    count = 0

    print("Rotary test started (Ctrl+C to stop)")
    print("Pins: CLK={}, DT={}, SW={}".format(ENC_CLK_PIN, ENC_DT_PIN, ENC_SW_PIN))
    print("count =", count)

    try:
        while True:
            clk_now = GPIO.input(ENC_CLK_PIN)
            if clk_now != last_clk:
                # if GPIO.input(ENC_DT_PIN) != clk_now:
                #     count += 1
                # else:
                #     count -= 1
                print("count =", count)
                print(GPIO.input(ENC_DT_PIN))
                last_clk = clk_now
            GPIO.input(ENC_DT_PIN)

            btn_now = GPIO.input(ENC_SW_PIN)
            now = time.monotonic()
            if btn_now != last_btn and (now - last_btn_time) >= BUTTON_DEBOUNCE_S:
                last_btn_time = now
                last_btn = btn_now
                if btn_now == 0:
                    print("button = PRESSED")
                else:
                    print("button = RELEASED")

            time.sleep(POLL_DELAY_S)
    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()
        print("Rotary test stopped")


if __name__ == "__main__":
    main()
