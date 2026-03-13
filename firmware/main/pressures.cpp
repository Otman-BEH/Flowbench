#include "pressures.h"
#include "esp_timer.h"
#include "esp_random.h"
#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "esp_log.h"
#include <string.h>

static const char *TAG = "pressures";


static const float BASES[NUM_CHANNELS]  = { 50.0f, 60.5f, 20.2f, 12.0f };
static const float NOISES[NUM_CHANNELS] = {  4.3f,  7.2f,  2.15f, 1.8f };

static float              s_latest[NUM_CHANNELS] = {};
static SemaphoreHandle_t  s_mutex                = nullptr;
static esp_timer_handle_t s_timer                = nullptr;

// RNG placeholder to simulate ADC reads of Pressure Transducers
static void sample_callback(void *arg)
{
    float fresh[NUM_CHANNELS];

    for (int i = 0; i < NUM_CHANNELS; i++)
    {
        float r = ((float)(esp_random() & 0xFFFF) / 32767.5f) - 1.0f;
        fresh[i] = BASES[i] + NOISES[i] * r;
    }

    xSemaphoreTakeFromISR(s_mutex, nullptr);
    memcpy(s_latest, fresh, sizeof(s_latest));
    xSemaphoreGiveFromISR(s_mutex, nullptr);
}

void pressures_init()
{
    s_mutex = xSemaphoreCreateMutex();

    sample_callback(nullptr);

    esp_timer_create_args_t args = {};
    args.callback = sample_callback;
    args.name     = "pressure_sample";

    esp_timer_create(&args, &s_timer);
    esp_timer_start_periodic(s_timer, SAMPLE_PERIOD_US);

    ESP_LOGI(TAG, "Pressure sampling started at %d us period", SAMPLE_PERIOD_US);
}

void pressures_get(float out[NUM_CHANNELS])
{
    xSemaphoreTake(s_mutex, portMAX_DELAY);
    memcpy(out, s_latest, sizeof(s_latest));
    xSemaphoreGive(s_mutex);
}
