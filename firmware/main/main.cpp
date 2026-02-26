#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <driver/gpio.h>

constexpr gpio_num_t LED_PIN = GPIO_NUM_2;
constexpr TickType_t BLINK_DELAY = pdMS_TO_TICKS(100);

extern "C" void app_main()
{
    gpio_config_t config = {
        .pin_bit_mask = (1ULL << LED_PIN),
        .mode         = GPIO_MODE_OUTPUT,
        .pull_up_en   = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type    = GPIO_INTR_DISABLE,
    };
    gpio_config(&config);

    bool state = false;
    while (true)
    {
        gpio_set_level(LED_PIN, state);
        state = !state;
        vTaskDelay(BLINK_DELAY);
    }
}