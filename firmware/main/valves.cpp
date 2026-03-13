#include "valves.h"
#include "driver/gpio.h"
#include "driver/ledc.h"
#include "esp_log.h"
#include <string.h>

static const char *TAG = "valves";

void valves_init()
{
    // Configure solenoid and LED GPIO pins as outputs
    gpio_config_t io = {};
    io.pin_bit_mask = (1ULL << PIN_LED) | (1ULL << PIN_SOL_1) | (1ULL << PIN_SOL_2);
    io.mode         = GPIO_MODE_OUTPUT;
    io.pull_up_en   = GPIO_PULLUP_DISABLE;
    io.pull_down_en = GPIO_PULLDOWN_DISABLE;
    io.intr_type    = GPIO_INTR_DISABLE;
    gpio_config(&io);

    gpio_set_level((gpio_num_t)PIN_LED,   0);
    gpio_set_level((gpio_num_t)PIN_SOL_1, 0);
    gpio_set_level((gpio_num_t)PIN_SOL_2, 0);

    ledc_timer_config_t timer = {};
    timer.speed_mode      = LEDC_LOW_SPEED_MODE;
    timer.duty_resolution = (ledc_timer_bit_t)SERVO_TIMER_RES_BITS;
    timer.timer_num       = LEDC_TIMER_0;
    timer.freq_hz         = SERVO_FREQ_HZ;
    timer.clk_cfg         = LEDC_AUTO_CLK;
    ledc_timer_config(&timer);

    ledc_channel_config_t channel = {};
    channel.speed_mode = LEDC_LOW_SPEED_MODE;
    channel.channel    = LEDC_CHANNEL_0;
    channel.timer_sel  = LEDC_TIMER_0;
    channel.gpio_num   = PIN_SERVO;
    channel.duty       = SERVO_DUTY_MIN;
    channel.hpoint     = 0;
    ledc_channel_config(&channel);

    ESP_LOGI(TAG, "Valves initialised");
}

// LED

void led_set(bool on)
{
    gpio_set_level((gpio_num_t)PIN_LED, on ? 1 : 0);
}

// Solenoid Valves

bool solenoid_set(const char *valve_name, bool open)
{
    gpio_num_t pin;

    if (strcmp(valve_name, "Solenoid Valve 1") == 0)
        pin = (gpio_num_t)PIN_SOL_1;
    else if (strcmp(valve_name, "Solenoid Valve 2") == 0)
        pin = (gpio_num_t)PIN_SOL_2;
    else
    {
        ESP_LOGW(TAG, "Unknown solenoid: %s", valve_name);
        return false;
    }

    gpio_set_level(pin, open ? 1 : 0);
    ESP_LOGI(TAG, "%s -> %s", valve_name, open ? "OPEN" : "CLOSED");
    return true;
}

// Servo valve

void servo_set_position(float position)
{
    if (position < 0.0f) position = 0.0f;
    if (position > 1.0f) position = 1.0f;

    uint32_t duty = (uint32_t)(SERVO_DUTY_MIN + position * (SERVO_DUTY_MAX - SERVO_DUTY_MIN));
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, duty);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
}

// Panic Button

void panic_close_all()
{
    gpio_set_level((gpio_num_t)PIN_SOL_1, 0);
    gpio_set_level((gpio_num_t)PIN_SOL_2, 0);
    servo_set_position(0.0f);
    led_set(false);
    ESP_LOGW(TAG, "PANIC — all valves closed");
}
