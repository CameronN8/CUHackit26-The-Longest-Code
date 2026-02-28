#include <U8g2lib.h>


U8G2_SSD1306_128X64_NONAME_F_SW_I2C oled1(U8G2_R0, /* clock=*/ 3, /* data=*/ 2, /* reset=*/ U8X8_PIN_NONE);


U8G2_SSD1306_128X64_NONAME_F_SW_I2C oled2(U8G2_R0, /* clock=*/ 6, /* data=*/ 5, /* reset=*/ U8X8_PIN_NONE);


U8G2_SSD1306_128X64_NONAME_F_SW_I2C oled3(U8G2_R0, /* clock=*/ 9, /* data=*/ 8, /* reset=*/ U8X8_PIN_NONE);

void setup() {
  oled1.begin();
  oled2.begin();
  oled3.begin();
}

void loop() {
  unsigned long seconds = millis() / 1000;

  // Display 1
  oled1.clearBuffer();
  oled1.setFont(u8g2_font_ncenB08_tr);
  oled1.drawStr(0, 15, "Display 1");
  oled1.setCursor(0, 35);
  oled1.print("Time: ");
  oled1.print(seconds);
  oled1.sendBuffer();

  // Display 2
  oled2.clearBuffer();
  oled2.setFont(u8g2_font_ncenB08_tr);
  oled2.drawStr(0, 15, "Display 2");
  oled2.setCursor(0, 35);
  oled2.print("Time: ");
  oled2.print(seconds);
  oled2.sendBuffer();

  // Display 3
  oled3.clearBuffer();
  oled3.setFont(u8g2_font_ncenB08_tr);
  oled3.drawStr(0, 15, "Display 3");
  oled3.setCursor(0, 35);
  oled3.print("Time: ");
  oled3.print(seconds);
  oled3.sendBuffer();

  delay(500);
}
