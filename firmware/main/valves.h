#pragma once

#include <stdbool.h>

#define PIN_LED          2    // Built-in LED
#define PIN_SOL_1        25   // Solenoid Valve 1
#define PIN_SOL_2        26   // Solenoid Valve 2
#define PIN_SERVO        27   // Servo Valve 1 (PWM via LEDC)

// Servo PWM Config
// Currently using placeholder vals
#define SERVO_FREQ_HZ        50
#define SERVO_TIMER_RES_BITS 14
#define SERVO_DUTY_MIN       819 // ~1 ms at 50 Hz
#define SERVO_DUTY_MAX       1638 // ~2 ms at 50 Hz

void valves_init();


void led_set(bool on);

bool solenoid_set(const char *valve_name, bool open);

void servo_set_position(float position);

void panic_close_all();
