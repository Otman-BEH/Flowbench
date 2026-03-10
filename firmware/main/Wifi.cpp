#include <esp_http_server.h>
#include <esp_wifi.h>
#include "esp_event.h"
#include "esp_netif.h"

constexpr char SSID[] = "Flowbench";
constexpr char PASSWORD[] = "12345678";
constexpr uint8_t CHANNEL = 1;
constexpr uint8_t MAX_CONNECTIONS = 1;

void wifi_init_ap()
{
    esp_netif_init();
    esp_event_loop_create_default();
    esp_netif_create_default_wifi_ap();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    esp_wifi_init(&cfg);

    wifi_config_t wifi_config = {};
    strncpy((char *)wifi_config.ap.ssid,     SSID,     sizeof(wifi_config.ap.ssid));
    strncpy((char *)wifi_config.ap.password, PASSWORD, sizeof(wifi_config.ap.password));
    wifi_config.ap.ssid_len       = strlen(SSID);
    wifi_config.ap.channel        = CHANNEL;
    wifi_config.ap.max_connection = MAX_CONNECTIONS;
    wifi_config.ap.authmode       = WIFI_AUTH_WPA2_PSK;

    esp_wifi_set_mode(WIFI_MODE_AP);
    esp_wifi_set_config(WIFI_IF_AP, &wifi_config);
    esp_wifi_start();
}

static esp_err_t root_handler(httpd_req_t *req)
{
    const char *response = "<h1>Hello from ESP32</h1>";
    httpd_resp_send(req, response, HTTPD_RESP_USE_STRLEN);
    return ESP_OK;
}

void start_webserver()
{
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    httpd_handle_t server = nullptr;

    if (httpd_start(&server, &config) == ESP_OK)
    {
        httpd_uri_t root = {
            .uri     = "/",
            .method  = HTTP_GET,
            .handler = root_handler,
        };
        httpd_register_uri_handler(server, &root);
    }
}
