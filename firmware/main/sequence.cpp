#include "sequence.h"
#include "valves.h"
#include "cJSON.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include <string.h>

static const char *TAG = "sequence";

static Sequence        s_sequence        = {};
static bool            s_loaded          = false;
static volatile bool   s_running         = false;
static volatile bool   s_abort_requested = false;
static TaskHandle_t    s_task_handle     = nullptr;


static void apply_actions(const SequenceStep *step)
{
    for (int i = 0; i < step->action_count; i++)
    {
        const ValveAction *a = &step->actions[i];

        if (a->type == ACTION_OPEN)
            solenoid_set(a->valve_name, true);
        else if (a->type == ACTION_CLOSE)
            solenoid_set(a->valve_name, false);
        else if (a->type == ACTION_PROFILE && a->point_count > 0)
            servo_set_position(a->points[0]);
    }
}

// Step through servo profile points for all PROFILE actions in a step.
static bool run_servo_profile(const SequenceStep *step)
{
    for (int i = 0; i < step->action_count; i++)
    {
        const ValveAction *a = &step->actions[i];
        if (a->type != ACTION_PROFILE) continue;

        for (int p = 0; p < a->point_count; p++)
        {
            if (s_abort_requested) return false;
            servo_set_position(a->points[p]);
            vTaskDelay(pdMS_TO_TICKS(a->interval_ms));
        }
    }
    return true;
}

static void sequence_task(void *arg)
{
    ESP_LOGI(TAG, "Sequence started (%d steps)", s_sequence.step_count);
    led_set(true);

    for (int i = 0; i < s_sequence.step_count; i++)
    {
        if (s_abort_requested) break;

        const SequenceStep *step = &s_sequence.steps[i];
        ESP_LOGI(TAG, "Step %d/%d", i + 1, s_sequence.step_count);

        // Apply solenoid actions immediately and start servo profile if present
        apply_actions(step);

        bool has_profile = false;
        for (int a = 0; a < step->action_count; a++)
            if (step->actions[a].type == ACTION_PROFILE) has_profile = true;

        if (step->hold)
        {
            if (has_profile)
                run_servo_profile(step);

            while (!s_abort_requested)
                vTaskDelay(pdMS_TO_TICKS(100));

            break;
        }
        else if (has_profile)
        {
            if (!run_servo_profile(step)) break;
        }
        else
        {
            int remaining = step->duration_ms;
            while (remaining > 0 && !s_abort_requested)
            {
                int slice = remaining > 10 ? 10 : remaining;
                vTaskDelay(pdMS_TO_TICKS(slice));
                remaining -= slice;
            }
        }
    }

    if (s_abort_requested)
    {
        panic_close_all();
        ESP_LOGW(TAG, "Sequence aborted");
    }
    else
    {
        led_set(false);
        ESP_LOGI(TAG, "Sequence complete");
    }

    s_running         = false;
    s_abort_requested = false;
    s_task_handle     = nullptr;
    vTaskDelete(nullptr);
}

bool sequence_load(const char *json_buf)
{
    if (s_running)
    {
        ESP_LOGW(TAG, "Cannot load while sequence is running");
        return false;
    }

    cJSON *root = cJSON_Parse(json_buf);
    if (!root)
    {
        ESP_LOGE(TAG, "JSON parse failed");
        return false;
    }

    cJSON *seq_array = cJSON_GetObjectItem(root, "sequence");
    if (!cJSON_IsArray(seq_array))
    {
        ESP_LOGE(TAG, "Missing 'sequence' array");
        cJSON_Delete(root);
        return false;
    }

    memset(&s_sequence, 0, sizeof(s_sequence));
    int step_count = cJSON_GetArraySize(seq_array);
    if (step_count > MAX_STEPS) step_count = MAX_STEPS;
    s_sequence.step_count = step_count;

    for (int si = 0; si < step_count; si++)
    {
        cJSON *step_json = cJSON_GetArrayItem(seq_array, si);
        SequenceStep *step = &s_sequence.steps[si];

        cJSON *dur = cJSON_GetObjectItem(step_json, "duration_ms");
        step->duration_ms = (dur && cJSON_IsNumber(dur)) ? (int)dur->valuedouble : 0;

        cJSON *hold = cJSON_GetObjectItem(step_json, "hold");
        step->hold = cJSON_IsTrue(hold);

        cJSON *actions_json = cJSON_GetObjectItem(step_json, "actions");
        int action_count = cJSON_IsArray(actions_json) ? cJSON_GetArraySize(actions_json) : 0;
        if (action_count > MAX_ACTIONS_PER_STEP) action_count = MAX_ACTIONS_PER_STEP;
        step->action_count = action_count;

        for (int ai = 0; ai < action_count; ai++)
        {
            cJSON *action_json = cJSON_GetArrayItem(actions_json, ai);
            ValveAction *action = &step->actions[ai];

            cJSON *valve  = cJSON_GetObjectItem(action_json, "valve");
            cJSON *act    = cJSON_GetObjectItem(action_json, "action");

            if (valve && cJSON_IsString(valve))
                strncpy(action->valve_name, valve->valuestring, MAX_VALVE_NAME_LEN - 1);

            if (act && cJSON_IsString(act))
            {
                if (strcmp(act->valuestring, "OPEN") == 0)
                    action->type = ACTION_OPEN;
                else if (strcmp(act->valuestring, "CLOSE") == 0)
                    action->type = ACTION_CLOSE;
                else if (strcmp(act->valuestring, "PROFILE") == 0)
                {
                    action->type = ACTION_PROFILE;

                    cJSON *interval = cJSON_GetObjectItem(action_json, "interval_ms");
                    action->interval_ms = (interval && cJSON_IsNumber(interval))
                                         ? (int)interval->valuedouble : 10;

                    cJSON *points_json = cJSON_GetObjectItem(action_json, "points");
                    if (cJSON_IsArray(points_json))
                    {
                        int pc = cJSON_GetArraySize(points_json);
                        if (pc > MAX_PROFILE_POINTS) pc = MAX_PROFILE_POINTS;
                        action->point_count = pc;
                        for (int pi = 0; pi < pc; pi++)
                        {
                            cJSON *pt = cJSON_GetArrayItem(points_json, pi);
                            action->points[pi] = cJSON_IsNumber(pt) ? (float)pt->valuedouble : 0.0f;
                        }
                    }
                }
            }
        }
    }

    cJSON_Delete(root);
    s_loaded = true;
    ESP_LOGI(TAG, "Loaded %d step(s)", s_sequence.step_count);
    return true;
}

bool sequence_run()
{
    if (!s_loaded)
    {
        ESP_LOGW(TAG, "No sequence loaded");
        return false;
    }
    if (s_running)
    {
        ESP_LOGW(TAG, "Already running");
        return false;
    }

    s_running         = true;
    s_abort_requested = false;

    xTaskCreate(sequence_task, "seq_task", 4096, nullptr, 5, &s_task_handle);
    return true;
}

void sequence_abort()
{
    s_abort_requested = true;
}

bool sequence_is_loaded()  { return s_loaded; }
bool sequence_is_running() { return s_running; }
