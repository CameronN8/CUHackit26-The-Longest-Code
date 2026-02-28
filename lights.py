from gpiozero import LED
from time import sleep
import threading

class clock:
    def __init__(self, pin=17, frequency=1):
        self.output = LED(pin)
        self.frequency = frequency
        self.delay = 1 / (2 * frequency)
        self._running = False
        self._thread = None

    def _run(self):
        while self._running:
            self.output.on()
            sleep(self.delay)
            self.output.off()
            sleep(self.delay)

    def start(self):
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join()
        self.output.off()
        print("Clock stopped")