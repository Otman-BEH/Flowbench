#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <driver/gpio.h>
#include <wifi.h>
#include <nvs_flash.h>

extern "C" void app_main()
{
    nvs_flash_init();
    wifi_init_ap();
    start_webserver();
}