#include <LiquidCrystal.h>

LiquidCrystal lcd(11, 6, 7, 8, 9, 10);

const int p1 = 2;
const int p2 = 3;
const int p3 = 4;

void setup() {
  pinMode(p1, INPUT_PULLUP);
  pinMode(p2, INPUT_PULLUP);
  pinMode(p3, INPUT_PULLUP);

  lcd.begin(16, 2);
  lcd.clear();
}

void loop() {
  int s1 = digitalRead(p1);
  int s2 = digitalRead(p2);
  int s3 = digitalRead(p3);

  s1 = (s1 == HIGH) ? 1 : 0;
  s2 = (s2 == HIGH) ? 1 : 0;
  s3 = (s3 == HIGH) ? 1 : 0;

  lcd.setCursor(0, 0);
  lcd.print("P1:");
  lcd.print(s1);
  lcd.print(" P2:");
  lcd.print(s2);
  lcd.print("   ");

  lcd.setCursor(0, 1);
  lcd.print("P3:");
  lcd.print(s3);
  lcd.print("           ");

  delay(100);
}