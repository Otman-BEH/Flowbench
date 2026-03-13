#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "nvs_flash.h"
#include "wifi.h"
#include "valves.h"
#include "pressures.h"

extern "C" void app_main()
{
    nvs_flash_init();
    valves_init();
    pressures_init();
    wifi_init_ap();
    start_webserver();
}
