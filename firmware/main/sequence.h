#pragma once

#include <stdbool.h>

#define MAX_STEPS            32
#define MAX_ACTIONS_PER_STEP 4
#define MAX_PROFILE_POINTS   200
#define MAX_VALVE_NAME_LEN   32

typedef enum
{
    ACTION_OPEN,
    ACTION_CLOSE,
    ACTION_PROFILE,
} ActionType;

typedef struct
{
    char       valve_name[MAX_VALVE_NAME_LEN];
    ActionType type;

    float points[MAX_PROFILE_POINTS];
    int   point_count;
    int   interval_ms;
} ValveAction;

typedef struct
{
    ValveAction actions[MAX_ACTIONS_PER_STEP];
    int         action_count;
    int         duration_ms;
    bool        hold;
} SequenceStep;

typedef struct
{
    SequenceStep steps[MAX_STEPS];
    int          step_count;
} Sequence;

bool sequence_load(const char *json_buf);

bool sequence_run();

void sequence_abort();

bool sequence_is_loaded();
bool sequence_is_running();
