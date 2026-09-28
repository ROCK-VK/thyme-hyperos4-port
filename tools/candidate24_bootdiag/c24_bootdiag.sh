#!/system/bin/sh

# C24 diagnostics only. This process never changes boot properties, display
# configuration, SELinux mode, partitions, or userdata contents.

TAG=C24BootDiag
DURATION_SECONDS=900
SAMPLE_SECONDS=10
DUMP_INTERVAL_SECONDS=60

emit() {
    /system/bin/log -p i -t "$TAG" "$*" 2>/dev/null
}

uptime_seconds() {
    read -r value rest < /proc/uptime
    value=${value%%.*}
    [ -n "$value" ] || value=unknown
    printf '%s' "$value"
}

prop_value() {
    value=$(/system/bin/getprop "$1" 2>/dev/null)
    [ -n "$value" ] || value='<empty-or-unreadable>'
    printf '%s' "$value"
}

pid_value() {
    value=$(/system/bin/pidof "$1" 2>/dev/null | /system/bin/toybox tr '\n' ',')
    [ -n "$value" ] || value=none
    printf '%s' "$value"
}

sample_state() {
    now=$(uptime_seconds)
    message="uptime=${now}s"
    for key in \
        sys.boot_completed \
        service.bootanim.exit \
        init.svc.bootanim \
        init.svc.surfaceflinger \
        init.svc.zygote \
        init.svc.zygote_secondary \
        init.svc.vold \
        init.svc.netd \
        persist.graphics.egl \
        ro.surface_flinger.default_composition_pixel_format; do
        message="$message $key=$(prop_value "$key")"
    done
    for process in \
        system_server zygote64 surfaceflinger bootanimation \
        com.android.systemui com.miui.systemui com.miui.home \
        com.android.settings com.google.android.setupwizard \
        com.android.provision com.miui.setupwizard; do
        message="$message pid.$process=$(pid_value "$process")"
    done
    emit "$message"
}

dump_filtered() {
    label=$1
    pattern=$2
    shift 2
    emit "dump.begin label=$label args=$*"
    /system/bin/toybox timeout 4 /system/bin/dumpsys "$@" 2>&1 \
        | /system/bin/toybox grep -iE "$pattern" \
        | /system/bin/toybox head -n 14 \
        | /system/bin/toybox cut -c 1-220 \
        | while IFS= read -r line; do emit "dump.$label $line"; done
    emit "dump.end label=$label"
}

sample_framework_and_display() {
    dump_filtered window \
        'mSystemBooted|mDisplayEnabled|mBootAnimationStopped|mCurrentFocus|mFocusedApp|mWakefulness|enableScreen|screen enabled|boot animation|error|exception|find service' \
        window
    dump_filtered activity \
        'mBooted|mBooting|mSystemReady|mDidUpdate|mBootCompleted|topResumedActivity|mResumedActivity|HomeActivity|SetupWizard|com\.android\.systemui|systemui|BOOT_COMPLETED|bootCompleted|find service|error|exception' \
        activity activities
    dump_filtered surfaceflinger \
        'display|active|physical|HWC|present|fence|vsync|power|composition|bootanimation|layer|error|exception' \
        SurfaceFlinger
    dump_filtered display_service \
        'DisplayDeviceInfo|mState|state=|enabled|physical|active|brightness|find service|error|exception' \
        display
    dump_filtered sf_display_ids \
        'display|id|error|usage|unknown|invalid' \
        SurfaceFlinger --display-id
    dump_filtered sf_bootanimation_layers \
        'bootanimation|boot animation|error|not found' \
        SurfaceFlinger --list

    emit 'dump.begin label=home_resolution'
    /system/bin/toybox timeout 4 /system/bin/cmd package resolve-activity --brief \
        -a android.intent.action.MAIN -c android.intent.category.HOME 2>&1 \
        | /system/bin/toybox head -n 4 \
        | /system/bin/toybox cut -c 1-220 \
        | while IFS= read -r line; do emit "dump.home_resolution $line"; done
    emit 'dump.end label=home_resolution'

    layer=$(/system/bin/toybox timeout 4 /system/bin/dumpsys SurfaceFlinger --list 2>/dev/null \
        | /system/bin/toybox grep -i 'bootanimation' \
        | /system/bin/toybox head -n 1)
    if [ -n "$layer" ]; then
        dump_filtered sf_bootanimation_latency \
            'refresh_period|present_time|^[[:space:]]*[0-9]' \
            SurfaceFlinger --latency "$layer"
    else
        emit 'sf_bootanimation_latency=not-sampled layer-not-listed'
    fi
}

start=$(uptime_seconds)
case "$start" in
    ''|*[!0-9]*) start=0 ;;
esac
deadline=$((start + DURATION_SECONDS))
next_dump=$start
emit "start uptime=${start}s duration=${DURATION_SECONDS}s interval=${SAMPLE_SECONDS}s dump_interval=${DUMP_INTERVAL_SECONDS}s"

while :; do
    sample_state
    now=$(uptime_seconds)
    case "$now" in
        ''|*[!0-9]*) now=$start ;;
    esac
    if [ "$now" -ge "$next_dump" ]; then
        sample_framework_and_display
        next_dump=$((now + DUMP_INTERVAL_SECONDS))
    fi
    if [ "$now" -ge "$deadline" ]; then
        break
    fi
    /system/bin/sleep "$SAMPLE_SECONDS"
done

emit "complete uptime=$(uptime_seconds)"
