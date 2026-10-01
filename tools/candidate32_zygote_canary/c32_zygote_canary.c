#define _GNU_SOURCE

#include <android/log.h>
#include <android/set_abort_message.h>

#include <stdlib.h>
#include <sys/prctl.h>
#include <sys/types.h>
#include <unistd.h>

static const char kTag[] = "THYME_C32_CANARY";
static const char kAbortMessage[] = "THYME_C32_CANARY_ABORT";

int main(void) {
    const int set_name_result = prctl(PR_SET_NAME, (unsigned long)"main", 0, 0, 0);
    const pid_t pid = getpid();

    __android_log_write(ANDROID_LOG_ERROR, kTag, "THYME_C32_CANARY_START");
    __android_log_print(ANDROID_LOG_ERROR, kTag,
                        "THYME_C32_CANARY_PID=%d COMM=main prctl_rc=%d",
                        (int)pid, set_name_result);
    __android_log_write(
            ANDROID_LOG_ERROR, kTag,
            "THYME_C32_CANARY_DOMAIN_EXPECTED=u:r:zygote:s0 actual=from-tombstone-label");

    android_set_abort_message(kAbortMessage);
    abort();
}
