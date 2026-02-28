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

        self.count = 0

    def _run(self):
        while self._running:
            self.count = self.count + 1
            if self.count == 1:
                self.output.on()
            else:
                self.output.off()
            if self.count == 19:
                self.count = 0
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