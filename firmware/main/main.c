#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "nvs_flash.h"
#include "lwip/sockets.h"
#include "driver/gpio.h"

#define AP_SSID         "Flowbench-DAQ"
#define AP_PASS         "testbench123"
#define SERVER_PORT     3333
#define BUF_SIZE        1024
#define LED_PIN         GPIO_NUM_2

static void gpio_init_pins(void) {
    gpio_reset_pin(LED_PIN);
    gpio_set_direction(LED_PIN, GPIO_MODE_OUTPUT);
    gpio_set_level(LED_PIN, 0);
}

static void wifi_init_ap(void) {
    esp_netif_init();
    esp_event_loop_create_default();
    esp_netif_create_default_wifi_ap();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    esp_wifi_init(&cfg);

    wifi_config_t wifi_config = {
        .ap = {
            .ssid           = AP_SSID,
            .password       = AP_PASS,
            .ssid_len       = strlen(AP_SSID),
            .max_connection = 1,
            .authmode       = WIFI_AUTH_WPA2_PSK,
        },
    };

    esp_wifi_set_mode(WIFI_MODE_AP);
    esp_wifi_set_config(WIFI_IF_AP, &wifi_config);
    esp_wifi_start();
}

static void led_blink(void *pv_parameters) {
    gpio_set_level(LED_PIN, 1);
    vTaskDelay(pdMS_TO_TICKS(1000));
    gpio_set_level(LED_PIN, 0);
    vTaskDelete(NULL);
}

static float read_pressures(void) {
    return 42.0f;
}

static void handle_command(const char *cmd) {
    if (strncmp(cmd, "LED", 3) == 0) {
        xTaskCreate(led_blink, "led_blink", 1024, NULL, 5, NULL);

    } else if (strncmp(cmd, "START", 5) == 0) {

    } else if (strncmp(cmd, "STOP", 4) == 0) {

    } else if (strncmp(cmd, "SET_RATE:", 9) == 0) {
        int rate = atoi(cmd + 9);

    }
}

static void tcp_server_task(void *pv_parameters) {
    char rx_buf[BUF_SIZE];
    char tx_buf[64];

    struct sockaddr_in server_addr = {
        .sin_family      = AF_INET,
        .sin_addr.s_addr = htonl(INADDR_ANY),
        .sin_port        = htons(SERVER_PORT),
    };

    int listen_sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    bind(listen_sock, (struct sockaddr *)&server_addr, sizeof(server_addr));
    listen(listen_sock, 1);

    while (1) {
        struct sockaddr_in client_addr;
        socklen_t addr_len = sizeof(client_addr);
        int client_sock = accept(listen_sock, (struct sockaddr *)&client_addr, &addr_len);

        while (1) {
            float pressure_vals = read_pressures();
            int len = snprintf(tx_buf, sizeof(tx_buf), "ADC:%.4f\n", pressure_vals);
            if (send(client_sock, tx_buf, len, 0) < 0) break;

            int rx_len = recv(client_sock, rx_buf, BUF_SIZE - 1, MSG_DONTWAIT);
            if (rx_len > 0) {
                rx_buf[rx_len] = '\0';
                rx_buf[strcspn(rx_buf, "\r\n")] = '\0';
                handle_command(rx_buf);
            } else if (rx_len == 0) {
                break;
            }

            vTaskDelay(pdMS_TO_TICKS(10));
        }

        close(client_sock);
    }
}

void app_main(void) {
    nvs_flash_init();
    gpio_init_pins();
    wifi_init_ap();
    xTaskCreate(tcp_server_task, "tcp_server_task", 4096, NULL, 5, NULL);
}