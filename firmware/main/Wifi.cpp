#include "wifi.h"
#include "valves.h"
#include "sequence.h"
#include "cJSON.h"
#include <esp_http_server.h>
#include <esp_wifi.h>
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_log.h"
#include <string.h>
#include "pressures.h"
#include "esp_random.h"
#include <stdlib.h>

static const char *TAG = "wifi";

constexpr char    SSID[]            = "Flowbench";
constexpr char    PASSWORD[]        = "12345678";
constexpr uint8_t CHANNEL           = 1;
constexpr uint8_t MAX_CONNECTIONS   = 1;
constexpr size_t  HTTP_BUF_SIZE     = 8192;


static char *read_body(httpd_req_t *req)
{
    if (req->content_len == 0 || req->content_len > HTTP_BUF_SIZE)
    {
        ESP_LOGE(TAG, "Bad content length: %d", req->content_len);
        return nullptr;
    }

    char *buf = (char *)malloc(req->content_len + 1);
    if (!buf) return nullptr;

    int total = 0, remaining = req->content_len;
    while (remaining > 0)
    {
        int received = httpd_req_recv(req, buf + total, remaining);
        if (received <= 0)
        {
            free(buf);
            return nullptr;
        }
        total     += received;
        remaining -= received;
    }
    buf[total] = '\0';
    return buf;
}

static void send_ok(httpd_req_t *req)
{
    httpd_resp_set_type(req, "application/json");
    httpd_resp_sendstr(req, "{\"status\":\"ok\"}");
}

static void send_error(httpd_req_t *req, const char *msg)
{
    httpd_resp_set_type(req, "application/json");
    httpd_resp_set_status(req, "400 Bad Request");
    char body[128];
    snprintf(body, sizeof(body), "{\"status\":\"error\",\"message\":\"%s\"}", msg);
    httpd_resp_sendstr(req, body);
}


static esp_err_t root_handler(httpd_req_t *req)
{
    httpd_resp_sendstr(req, "{\"device\":\"FlowBench ESP32\"}");
    return ESP_OK;
}


static esp_err_t sequence_handler(httpd_req_t *req)
{
    char *buf = read_body(req);
    if (!buf)
    {
        send_error(req, "Failed to read body");
        return ESP_FAIL;
    }

    bool ok = sequence_load(buf);
    free(buf);

    if (!ok)
    {
        send_error(req, "Invalid sequence JSON");
        return ESP_FAIL;
    }

    led_set(true);   // LED on means sequence has been received
    send_ok(req);
    return ESP_OK;
}


static esp_err_t run_handler(httpd_req_t *req)
{
    if (!sequence_is_loaded())
    {
        send_error(req, "No sequence loaded");
        return ESP_FAIL;
    }
    if (sequence_is_running())
    {
        send_error(req, "Already running");
        return ESP_FAIL;
    }

    bool ok = sequence_run();
    if (!ok)
    {
        send_error(req, "Failed to start sequence");
        return ESP_FAIL;
    }

    send_ok(req);
    return ESP_OK;
}

static esp_err_t valve_handler(httpd_req_t *req)
{
    char *buf = read_body(req);
    if (!buf)
    {
        send_error(req, "Failed to read body");
        return ESP_FAIL;
    }

    cJSON *root = cJSON_Parse(buf);
    free(buf);

    if (!root)
    {
        send_error(req, "Invalid JSON");
        return ESP_FAIL;
    }

    cJSON *valve  = cJSON_GetObjectItem(root, "valve");
    cJSON *action = cJSON_GetObjectItem(root, "action");

    if (!cJSON_IsString(valve) || !cJSON_IsString(action))
    {
        cJSON_Delete(root);
        send_error(req, "Missing valve or action field");
        return ESP_FAIL;
    }

    const char *valve_name = valve->valuestring;
    const char *action_str = action->valuestring;

    if (strcmp(valve_name, "Servo Valve 1") == 0)
    {
        // Manual servo opening
        servo_set_position(strcmp(action_str, "OPEN") == 0 ? 1.0f : 0.0f);
    }
    else
    {
        bool open = strcmp(action_str, "OPEN") == 0;
        if (!solenoid_set(valve_name, open))
        {
            cJSON_Delete(root);
            send_error(req, "Unknown valve name");
            return ESP_FAIL;
        }
    }

    cJSON_Delete(root);
    send_ok(req);
    return ESP_OK;
}

static esp_err_t panic_handler(httpd_req_t *req)
{
    sequence_abort();
    panic_close_all();
    send_ok(req);
    return ESP_OK;
}

static esp_err_t pressures_handler(httpd_req_t *req)
{
    float values[NUM_CHANNELS];
    pressures_get(values);

    char body[128];
    snprintf(body, sizeof(body),
        "{\"pressures\":[%.3f,%.3f,%.3f,%.3f]}",
        values[0], values[1], values[2], values[3]);

    httpd_resp_set_type(req, "application/json");
    httpd_resp_sendstr(req, body);
    return ESP_OK;
}


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

    ESP_LOGI(TAG, "AP started — SSID: %s", SSID);
}


void start_webserver()
{
    httpd_config_t config  = HTTPD_DEFAULT_CONFIG();
    config.max_uri_handlers = 8;
    httpd_handle_t server  = nullptr;

    if (httpd_start(&server, &config) != ESP_OK)
    {
        ESP_LOGE(TAG, "Failed to start HTTP server");
        return;
    }

    httpd_uri_t routes[] = {
        { .uri = "/",          .method = HTTP_GET,  .handler = root_handler      },
        { .uri = "/sequence",  .method = HTTP_POST, .handler = sequence_handler  },
        { .uri = "/run",       .method = HTTP_POST, .handler = run_handler       },
        { .uri = "/valve",     .method = HTTP_POST, .handler = valve_handler     },
        { .uri = "/panic",     .method = HTTP_POST, .handler = panic_handler     },
        { .uri = "/pressures", .method = HTTP_GET,  .handler = pressures_handler },
    };

    for (auto &r : routes)
        httpd_register_uri_handler(server, &r);

    ESP_LOGI(TAG, "Webserver started on port %d", config.server_port);
}
