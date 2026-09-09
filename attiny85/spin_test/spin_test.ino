/**
 * Pulse test — open loop, no feedback.
 * Outputs fixed 100 pulses/s (100 Hz, 50% duty) on PB0.
 * 5 ms HIGH / 5 ms LOW via busy-wait on micros() for stable timing.
 * PB0 (pin 5) -> driver VR (through RC filter if fitted).
 */
#ifndef F_CPU
#define F_CPU 8000000UL
#endif

#include <avr/io.h>

#define PWM_PIN 0
#define HALF_PERIOD_US 5000UL // 100 Hz, 50%

void setup() {
  pinMode(PWM_PIN, OUTPUT);
  digitalWrite(PWM_PIN, LOW);
  delay(2000); // driver enable/arm time
}

void loop() {
  unsigned long t0 = micros();
  digitalWrite(PWM_PIN, HIGH);
  while ((unsigned long)(micros() - t0) < HALF_PERIOD_US) {}
  t0 += HALF_PERIOD_US;
  digitalWrite(PWM_PIN, LOW);
  while ((unsigned long)(micros() - t0) < HALF_PERIOD_US) {}
}
