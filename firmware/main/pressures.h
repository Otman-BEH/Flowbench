#pragma once

#include <stdint.h>

#define NUM_CHANNELS     4
#define SAMPLE_PERIOD_US 50000

void pressures_init();
void pressures_get(float out[NUM_CHANNELS]);
