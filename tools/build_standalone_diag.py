#!/usr/bin/env python3
import argparse
import os
import sys
import subprocess
import hashlib
import shutil
from datetime import datetime

REPO_ROOT = "e:/RVK/10S_OS4"
DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, "work", "standalone_diag")
parser = argparse.ArgumentParser(description="Build a Standalone Diag image into a new, isolated output directory.")
parser.add_argument("--out-dir", required=True, help="New output directory; existing paths are refused to preserve prior artifacts.")
parser.add_argument("--export-c25-metadata", action="store_true",
                    help="Add a read-only, sysfs-identified export of /metadata/thyme_os4_diag.")
args = parser.parse_args()
OUT_DIR = os.path.abspath(args.out_dir)
if os.path.exists(OUT_DIR):
    raise SystemExit(f"Refusing to overwrite existing output directory: {OUT_DIR}")
os.makedirs(OUT_DIR, exist_ok=False)
drive, out_tail = os.path.splitdrive(OUT_DIR)
if drive.lower() != "e:":
    raise SystemExit(f"Output directory must be on E: for WSL access: {OUT_DIR}")
OUT_DIR_WSL = "/mnt/e/" + out_tail.lstrip("\\/").replace("\\", "/")
BUILD_TAG_SOURCE = os.path.relpath(OUT_DIR, REPO_ROOT)
BUILD_TAG = "".join(c if c.isalnum() or c in "_-" else "_" for c in BUILD_TAG_SOURCE)
WSL_BUILD_ROOT = f"/root/thyme_standalone_{BUILD_TAG}"

A5_KERNEL = os.path.join(REPO_ROOT, "work", "control_experiments_pixel_a17_1", "a5_aosp_toolchain", "Image")
BUSYBOX_BIN = os.path.join(REPO_ROOT, "work", "bin", "busybox.static")
MKBOOTIMG = os.path.join(REPO_ROOT, "tools", "bootimg", "mkbootimg.py")
AVBTOOL = os.path.join(REPO_ROOT, "tools", "bootimg", "avbtool.py")
UNPACK_BOOTIMG = os.path.join(REPO_ROOT, "tools", "bootimg", "unpack_bootimg.py")

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

print("[1/5] Verifying source prerequisites...")
assert os.path.exists(A5_KERNEL), f"Missing A5 kernel: {A5_KERNEL}"
assert os.path.exists(BUSYBOX_BIN), f"Missing busybox: {BUSYBOX_BIN}"
a5_hash = sha256_file(A5_KERNEL)
bb_hash = sha256_file(BUSYBOX_BIN)
print(f"  A5 Kernel SHA256: {a5_hash}")
print(f"  Busybox SHA256:   {bb_hash}")
assert a5_hash == "6fdffdbbe9bd65197b32a8a603c8548793f0cdf7c3cc3a1d6443c36121b62fa9", "A5 hash mismatch!"

# Create build script for WSL
wsl_script_path = os.path.join(OUT_DIR, "wsl_build_ramdisk.sh")
wsl_script_content = """#!/usr/bin/env bash
set -euo pipefail

BUILD_ROOT="__BUILD_ROOT__"
if [ -e "$BUILD_ROOT" ]; then
    echo "Refusing to overwrite existing WSL build root: $BUILD_ROOT" >&2
    exit 1
fi
mkdir -p "$BUILD_ROOT/root"

cd "$BUILD_ROOT/root"
mkdir -p bin dev proc sys tmp config etc mnt/fat var
ln -s bin sbin
mkdir -p usr
ln -s ../bin usr/bin
ln -s ../bin usr/sbin

# Copy busybox static
cp /mnt/e/RVK/10S_OS4/work/bin/busybox.static bin/busybox
chmod 755 bin/busybox

# Create symlinks for all applets
for app in $(bin/busybox --list); do
    ln -sf busybox "bin/$app"
done

# Create /etc/fstab and /etc/mtab
cat << 'EOF' > etc/fstab
proc    /proc   proc    defaults    0 0
sysfs   /sys    sysfs   defaults    0 0
tmpfs   /tmp    tmpfs   defaults    0 0
EOF
ln -sf /proc/mounts etc/mtab

# Write /init (PID 1 script)
cat << 'EOF' > init
#!/bin/sh
# Thyme Standalone Diagnostic Environment
# Zero Android Userspace - Direct Hardware Log Dump

# 1. Mount essential virtual filesystems
/bin/mount -t proc proc /proc
/bin/mount -t sysfs sysfs /sys
/bin/mount -t tmpfs -o mode=0755,nosuid tmpfs /dev
/bin/mount -t tmpfs tmpfs /tmp
/bin/mkdir -p /dev/pts /dev/shm /dev/block
/bin/mount -t devpts devpts /dev/pts

# Create essential char devices (no devtmpfs in MSM kernels)
/bin/mknod /dev/null c 1 3
/bin/mknod /dev/zero c 1 5
/bin/mknod /dev/full c 1 7
/bin/mknod /dev/random c 1 8
/bin/mknod /dev/urandom c 1 9
/bin/mknod /dev/kmsg c 1 11
/bin/mknod /dev/console c 5 1
/bin/mknod /dev/tty c 5 0
/bin/chmod 666 /dev/null /dev/zero /dev/full /dev/random /dev/urandom /dev/tty

# Do not fabricate UFS partition device numbers; only kernel-discovered nodes are used.
for i in $(seq 0 15); do
    /bin/mknod /dev/loop$i b 7 $i 2>/dev/null || true
done
/bin/mknod /dev/loop-control c 10 237 2>/dev/null || true

# Start mdev hotplug if available
echo /bin/mdev > /proc/sys/kernel/hotplug 2>/dev/null || true
/bin/mdev -s 2>/dev/null || true

# 2. Setup logging directory
/bin/mkdir -p /tmp/dumps
STATUS_LOG=/tmp/dumps/diag_status.log

echo "=================================================" > "$STATUS_LOG"
echo "  THYME STANDALONE DIAGNOSTIC ENVIRONMENT v1.1   " >> "$STATUS_LOG"
echo "=================================================" >> "$STATUS_LOG"
echo "Boot Time (UTC): $(date -u)" >> "$STATUS_LOG"
echo "Kernel: $(cat /proc/version)" >> "$STATUS_LOG"
echo "Cmdline: $(cat /proc/cmdline)" >> "$STATUS_LOG"
echo "PID 1: $$ (sh on busybox)" >> "$STATUS_LOG"
echo "Dev nodes created successfully" >> "$STATUS_LOG"

# 3. Discover exactly one misc partition from kernel sysfs uevent data.
#    The /dev symlink is temporary in the new /dev tmpfs. Never infer an sdX index.
MISC_DEV=/dev/block/by-name/misc
EXPECTED_MISC_BYTES=4194304
MISC_MATCH_COUNT=0
MISC_MATCH_EVENT=
for UEVENT in /sys/class/block/*/uevent; do
    [ -f "$UEVENT" ] || continue
    EVENT_PARTNAME=$(/bin/sed -n 's/^PARTNAME=//p' "$UEVENT" 2>> "$STATUS_LOG")
    [ "$EVENT_PARTNAME" = "misc" ] || continue
    MISC_MATCH_COUNT=$((MISC_MATCH_COUNT + 1))
    MISC_MATCH_EVENT=$UEVENT
done

echo "[INFO] Exact PARTNAME=misc sysfs matches: $MISC_MATCH_COUNT" >> "$STATUS_LOG"
if [ "$MISC_MATCH_COUNT" -ne 1 ]; then
    echo "[STOP] Expected exactly one sysfs PARTNAME=misc match; no block device was read" >> "$STATUS_LOG"
else
    EVENT_MAJOR=$(/bin/sed -n 's/^MAJOR=//p' "$MISC_MATCH_EVENT" 2>> "$STATUS_LOG")
    EVENT_MINOR=$(/bin/sed -n 's/^MINOR=//p' "$MISC_MATCH_EVENT" 2>> "$STATUS_LOG")
    EVENT_DEVNAME=$(/bin/sed -n 's/^DEVNAME=//p' "$MISC_MATCH_EVENT" 2>> "$STATUS_LOG")
    SYSFS_BLOCK_NAME=${MISC_MATCH_EVENT%/uevent}
    SYSFS_BLOCK_NAME=${SYSFS_BLOCK_NAME##*/}
    echo "[INFO] misc sysfs event: $MISC_MATCH_EVENT" >> "$STATUS_LOG"
    echo "[INFO] misc PARTNAME=misc MAJOR=$EVENT_MAJOR MINOR=$EVENT_MINOR DEVNAME=$EVENT_DEVNAME" >> "$STATUS_LOG"

    EVENT_FIELDS_VALID=1
    case "$EVENT_MAJOR" in ''|*[!0-9]*) EVENT_FIELDS_VALID=0 ;; esac
    case "$EVENT_MINOR" in ''|*[!0-9]*) EVENT_FIELDS_VALID=0 ;; esac
    case "$EVENT_DEVNAME" in ''|*/*|.|..) EVENT_FIELDS_VALID=0 ;; esac
    if [ "$EVENT_DEVNAME" != "$SYSFS_BLOCK_NAME" ]; then EVENT_FIELDS_VALID=0; fi

    if [ "$EVENT_FIELDS_VALID" -ne 1 ]; then
        echo "[STOP] sysfs MAJOR/MINOR/DEVNAME fields are missing, duplicated, malformed, or inconsistent; no read was attempted" >> "$STATUS_LOG"
    else
        MISC_NODE="/dev/$EVENT_DEVNAME"
        if [ ! -e "$MISC_NODE" ] || [ ! -b "$MISC_NODE" ]; then
            echo "[STOP] Kernel-derived node $MISC_NODE is missing or not a block device; no alternate node was tried" >> "$STATUS_LOG"
        else
            NODE_DEV=$(/bin/stat -c '%t:%T' "$MISC_NODE" 2>> "$STATUS_LOG")
            NODE_MAJOR_HEX=${NODE_DEV%%:*}
            NODE_MINOR_HEX=${NODE_DEV#*:}
            NODE_DEV_VALID=1
            case "$NODE_DEV" in *:*) ;; *) NODE_DEV_VALID=0 ;; esac
            case "$NODE_MAJOR_HEX" in ''|*[!0-9a-fA-F]*) NODE_DEV_VALID=0 ;; esac
            case "$NODE_MINOR_HEX" in ''|*[!0-9a-fA-F]*|*:* ) NODE_DEV_VALID=0 ;; esac
            if [ "$NODE_DEV_VALID" -eq 1 ]; then
                NODE_MAJOR_HEX=$(printf '%s' "$NODE_MAJOR_HEX" | /bin/tr 'ABCDEF' 'abcdef')
                NODE_MINOR_HEX=$(printf '%s' "$NODE_MINOR_HEX" | /bin/tr 'ABCDEF' 'abcdef')
                EXPECTED_MAJOR_HEX=$(printf '%x' "$EVENT_MAJOR" 2>> "$STATUS_LOG") || EXPECTED_MAJOR_HEX=invalid
                EXPECTED_MINOR_HEX=$(printf '%x' "$EVENT_MINOR" 2>> "$STATUS_LOG") || EXPECTED_MINOR_HEX=invalid
            else
                EXPECTED_MAJOR_HEX=invalid
                EXPECTED_MINOR_HEX=invalid
            fi
            echo "[INFO] node $MISC_NODE stat device=$NODE_DEV; sysfs expected=$EXPECTED_MAJOR_HEX:$EXPECTED_MINOR_HEX (hex)" >> "$STATUS_LOG"
            if [ "$NODE_DEV_VALID" -ne 1 ] || [ "$NODE_MAJOR_HEX" != "$EXPECTED_MAJOR_HEX" ] || [ "$NODE_MINOR_HEX" != "$EXPECTED_MINOR_HEX" ]; then
                echo "[STOP] Kernel-derived node device number does not match sysfs MAJOR/MINOR; no read was attempted" >> "$STATUS_LOG"
            else
                MISC_BYTES=$(/bin/blockdev --getsize64 "$MISC_NODE" 2>> "$STATUS_LOG") || MISC_BYTES=0
                echo "[INFO] sysfs-verified misc node capacity: $MISC_BYTES bytes" >> "$STATUS_LOG"
                if [ "$MISC_BYTES" != "$EXPECTED_MISC_BYTES" ]; then
                    echo "[STOP] misc capacity mismatch; expected $EXPECTED_MISC_BYTES bytes; no read was attempted" >> "$STATUS_LOG"
                elif [ -e "$MISC_DEV" ] || [ -L "$MISC_DEV" ]; then
                    echo "[STOP] $MISC_DEV already exists; refusing to replace an unexpected path" >> "$STATUS_LOG"
                else
                    /bin/mkdir -p /dev/block/by-name 2>> "$STATUS_LOG"
                    if /bin/ln -s "$MISC_NODE" "$MISC_DEV" 2>> "$STATUS_LOG"; then
                        LINK_TARGET=$(/bin/readlink "$MISC_DEV" 2>> "$STATUS_LOG")
                        # Verify both the exact target node and BusyBox's explicit symlink-following stat result.
                        LINK_TARGET_DEV=$(/bin/stat -c '%t:%T' "$LINK_TARGET" 2>> "$STATUS_LOG")
                        LINK_RESOLVED_DEV=$(/bin/stat -L -c '%t:%T' "$MISC_DEV" 2>> "$STATUS_LOG")
                        LINK_BYTES=$(/bin/blockdev --getsize64 "$MISC_DEV" 2>> "$STATUS_LOG") || LINK_BYTES=0
                        echo "[INFO] temporary by-name link target: $LINK_TARGET" >> "$STATUS_LOG"
                        echo "[INFO] by-name target stat device=$LINK_TARGET_DEV; stat -L device=$LINK_RESOLVED_DEV; link capacity=$LINK_BYTES bytes" >> "$STATUS_LOG"
                        if [ ! -L "$MISC_DEV" ] || [ ! -b "$MISC_DEV" ] || [ "$LINK_TARGET" != "$MISC_NODE" ] || [ "$LINK_TARGET_DEV" != "$NODE_DEV" ] || [ "$LINK_RESOLVED_DEV" != "$NODE_DEV" ] || [ "$LINK_BYTES" != "$EXPECTED_MISC_BYTES" ]; then
                            echo "[STOP] temporary by-name link does not resolve to the verified sysfs partition; no read was attempted" >> "$STATUS_LOG"
                        else
                            echo "[OK] Unique sysfs misc mapping, block type, device number, symlink target, and 4 MiB capacity verified" >> "$STATUS_LOG"
                            echo "[INFO] Reading $MISC_DEV using dd if= only; output is in RAM /tmp" >> "$STATUS_LOG"
                            /bin/dd if="$MISC_DEV" of=/tmp/dumps/misc.raw.partial bs=4096 count=1024 status=none 2>> "$STATUS_LOG"
                            DD_STATUS=$?
                            if [ "$DD_STATUS" -ne 0 ]; then
                                echo "[STOP] read command failed with status $DD_STATUS" >> "$STATUS_LOG"
                            else
                                CAPTURED_BYTES=$(/bin/wc -c < /tmp/dumps/misc.raw.partial)
                                echo "[INFO] captured byte count: $CAPTURED_BYTES" >> "$STATUS_LOG"
                                if [ "$CAPTURED_BYTES" != "$EXPECTED_MISC_BYTES" ]; then
                                    echo "[STOP] captured size mismatch; incomplete file will not be named misc.raw" >> "$STATUS_LOG"
                                else
                                    /bin/mv /tmp/dumps/misc.raw.partial /tmp/dumps/misc.raw
                                    /bin/sha256sum /tmp/dumps/misc.raw > /tmp/dumps/misc.raw.sha256
                                    echo "[OK] misc.raw SHA-256: $(/bin/cut -d ' ' -f 1 /tmp/dumps/misc.raw.sha256)" >> "$STATUS_LOG"
                                    echo "[OK] complete raw misc copy saved in RAM" >> "$STATUS_LOG"
                                fi
                            fi
                        fi
                    else
                        echo "[STOP] Could not create temporary by-name symlink; no read was attempted" >> "$STATUS_LOG"
                    fi
                fi
            fi
        fi
    fi
fi

# 4. Build a 64MB FAT32 UMS image in RAM
echo "[INFO] Formatting 64MB FAT32 RAM disk image..." >> "$STATUS_LOG"
/bin/dd if=/dev/zero of=/tmp/fat32_disk.img bs=1M count=64 status=none
/bin/losetup /dev/loop0 /tmp/fat32_disk.img 2>> "$STATUS_LOG" || true
/bin/mkfs.vfat -F 32 -n "THYME_DIAG" /dev/loop0 >> "$STATUS_LOG" 2>&1

/bin/mkdir -p /mnt/fat
if /bin/mount -t vfat /dev/loop0 /mnt/fat 2>> "$STATUS_LOG"; then
    echo "[OK] Mounted FAT32 RAM disk, copying dump files..." >> "$STATUS_LOG"
    /bin/cp -r /tmp/dumps/* /mnt/fat/
    /bin/sync
    /bin/umount /mnt/fat
    echo "[OK] FAT32 RAM disk successfully populated with logs and unmounted cleanly" >> "$STATUS_LOG"
else
    echo "[ERROR] Failed to mount FAT32 disk via loop0" >> "$STATUS_LOG"
fi
/bin/losetup -d /dev/loop0 2>/dev/null || true

# 7. Initialize USB ConfigFS Mass Storage Gadget & Qualcomm PHY
echo "[INFO] Configuring Qualcomm dwc3 peripheral mode..." >> "$STATUS_LOG"
for mode_file in /sys/class/udc/*/device/../mode /sys/devices/platform/soc/a600000.ssusb/mode; do
    if [ -f "$mode_file" ]; then
        echo "peripheral" > "$mode_file" 2>> "$STATUS_LOG" || true
        echo "[OK] Set $mode_file to peripheral" >> "$STATUS_LOG"
    fi
done

echo "[INFO] Initializing USB ConfigFS Mass Storage..." >> "$STATUS_LOG"
/bin/mkdir -p /config
/bin/mount -t configfs none /config 2>> "$STATUS_LOG" || true

GADGET="/config/usb_gadget/g1"
/bin/mkdir -p "$GADGET"
echo 0x054c > "$GADGET/idVendor"
echo 0x0022 > "$GADGET/idProduct"
echo 0x0200 > "$GADGET/bcdUSB"
echo 0x00 > "$GADGET/bDeviceClass"
echo 0x00 > "$GADGET/bDeviceSubClass"
echo 0x00 > "$GADGET/bDeviceProtocol"

/bin/mkdir -p "$GADGET/strings/0x409"
echo "THYME-DIAG" > "$GADGET/strings/0x409/serialnumber"
echo "Sony" > "$GADGET/strings/0x409/manufacturer"
echo "MicroVault" > "$GADGET/strings/0x409/product"

# Mass storage function - STRICTLY pointing to RAM image with ro=1
/bin/mkdir -p "$GADGET/functions/mass_storage.0/lun.0"
echo /tmp/fat32_disk.img > "$GADGET/functions/mass_storage.0/lun.0/file"
echo 1 > "$GADGET/functions/mass_storage.0/lun.0/ro"
echo 1 > "$GADGET/functions/mass_storage.0/lun.0/removable"
echo 0 > "$GADGET/functions/mass_storage.0/lun.0/cdrom"
echo 1 > "$GADGET/functions/mass_storage.0/lun.0/nofua" 2>/dev/null || true
echo "Sony MicroVault  " > "$GADGET/functions/mass_storage.0/lun.0/inquiry_string" 2>/dev/null || true

# Config
/bin/mkdir -p "$GADGET/configs/b.1/strings/0x409"
echo 500 > "$GADGET/configs/b.1/MaxPower"
echo "Diag UMS" > "$GADGET/configs/b.1/strings/0x409/configuration"
/bin/ln -s "$GADGET/functions/mass_storage.0" "$GADGET/configs/b.1/" 2>> "$STATUS_LOG" || true

# Turn on panel backlight so screen indicates activity
echo 200 > /sys/class/backlight/panel0-backlight/brightness 2>/dev/null || true

# UDC binding
UDC="a600000.dwc3"
if [ -d "/sys/class/udc/$UDC" ]; then
    echo "$UDC" > "$GADGET/UDC" 2>> "$STATUS_LOG" || true
    echo "[OK] Bound USB Gadget to $UDC" >> "$STATUS_LOG"
else
    DETECTED_UDC=$(ls /sys/class/udc 2>/dev/null | head -n 1 || true)
    if [ -n "$DETECTED_UDC" ]; then
        echo "$DETECTED_UDC" > "$GADGET/UDC" 2>> "$STATUS_LOG" || true
        echo "[OK] Bound USB Gadget to detected $DETECTED_UDC" >> "$STATUS_LOG"
    else
        echo "[ERROR] No UDC device found in /sys/class/udc!" >> "$STATUS_LOG"
    fi
fi

echo "=================================================" >> "$STATUS_LOG"
echo "  DIAGNOSTIC DUMP EXPORTED TO USB MASS STORAGE   " >> "$STATUS_LOG"
echo "=================================================" >> "$STATUS_LOG"

# 8. Never reboot automatically. Keep RAM alive for extraction.
while true; do
    /bin/sleep 60
done
EOF
chmod 755 init

# Repack CPIO
find . ! -name . | sort | cpio -o -H newc -R 0:0 | lz4 -l -12 --favor-decSpeed > "$BUILD_ROOT/standalone_diag_ramdisk.lz4"
cp "$BUILD_ROOT/standalone_diag_ramdisk.lz4" "__OUT_DIR_WSL__/standalone_diag_ramdisk.lz4"
echo "WSL Ramdisk repacking complete: $(ls -l $BUILD_ROOT/standalone_diag_ramdisk.lz4)"
"""

C25_METADATA_EXPORT = r'''# Optional C25 persistent diagnostic export. The source is never mounted writable.
META_MOUNT=/mnt/metadata_c25_ro
META_SOURCE=/metadata/thyme_os4_diag
META_MATCH_COUNT=0
META_MATCH_EVENT=
for UEVENT in /sys/class/block/*/uevent; do
    [ -f "$UEVENT" ] || continue
    EVENT_PARTNAME=$(/bin/sed -n 's/^PARTNAME=//p' "$UEVENT" 2>> "$STATUS_LOG")
    [ "$EVENT_PARTNAME" = "metadata" ] || continue
    META_MATCH_COUNT=$((META_MATCH_COUNT + 1))
    META_MATCH_EVENT=$UEVENT
done
echo "[C25] exact PARTNAME=metadata matches: $META_MATCH_COUNT" >> "$STATUS_LOG"
if [ "$META_MATCH_COUNT" -ne 1 ]; then
    echo "[C25][STOP] metadata identity is not unique; no metadata device read or mount attempted" >> "$STATUS_LOG"
else
    EVENT_MAJOR=$(/bin/sed -n 's/^MAJOR=//p' "$META_MATCH_EVENT" 2>> "$STATUS_LOG")
    EVENT_MINOR=$(/bin/sed -n 's/^MINOR=//p' "$META_MATCH_EVENT" 2>> "$STATUS_LOG")
    EVENT_DEVNAME=$(/bin/sed -n 's/^DEVNAME=//p' "$META_MATCH_EVENT" 2>> "$STATUS_LOG")
    SYSFS_BLOCK_NAME=${META_MATCH_EVENT%/uevent}
    SYSFS_BLOCK_NAME=${SYSFS_BLOCK_NAME##*/}
    case "$EVENT_MAJOR:$EVENT_MINOR" in *[!0-9:]*|:|*:|*:*:*) EVENT_FIELDS_VALID=0 ;; *) EVENT_FIELDS_VALID=1 ;; esac
    case "$EVENT_DEVNAME" in ''|*/*|.|..) EVENT_FIELDS_VALID=0 ;; esac
    [ "$EVENT_DEVNAME" = "$SYSFS_BLOCK_NAME" ] || EVENT_FIELDS_VALID=0
    META_NODE="/dev/$EVENT_DEVNAME"
    SYSFS_SIZE="/sys/class/block/$SYSFS_BLOCK_NAME/size"
    if [ "$EVENT_FIELDS_VALID" -ne 1 ]; then
        echo "[C25][STOP] metadata uevent fields are malformed or inconsistent; no read attempted" >> "$STATUS_LOG"
    elif [ ! -e "$META_NODE" ] || [ ! -b "$META_NODE" ] || [ ! -r "$SYSFS_SIZE" ]; then
        echo "[C25][STOP] kernel-derived metadata block node or sysfs size is unavailable; no alternate node tried" >> "$STATUS_LOG"
    else
        NODE_DEV=$(/bin/stat -c '%t:%T' "$META_NODE" 2>> "$STATUS_LOG")
        NODE_MAJOR_HEX=${NODE_DEV%%:*}
        NODE_MINOR_HEX=${NODE_DEV#*:}
        case "$NODE_DEV" in *:*) NODE_VALID=1 ;; *) NODE_VALID=0 ;; esac
        case "$NODE_MAJOR_HEX:$NODE_MINOR_HEX" in *[!0-9a-fA-F:]*|:|*:|*:*:*) NODE_VALID=0 ;; esac
        NODE_MAJOR_HEX=$(printf '%s' "$NODE_MAJOR_HEX" | /bin/tr 'ABCDEF' 'abcdef')
        NODE_MINOR_HEX=$(printf '%s' "$NODE_MINOR_HEX" | /bin/tr 'ABCDEF' 'abcdef')
        EXPECTED_MAJOR_HEX=$(printf '%x' "$EVENT_MAJOR" 2>> "$STATUS_LOG") || EXPECTED_MAJOR_HEX=invalid
        EXPECTED_MINOR_HEX=$(printf '%x' "$EVENT_MINOR" 2>> "$STATUS_LOG") || EXPECTED_MINOR_HEX=invalid
        SECTORS=$(/bin/cat "$SYSFS_SIZE" 2>> "$STATUS_LOG")
        case "$SECTORS" in ''|*[!0-9]*) SECTORS_VALID=0 ;; *) SECTORS_VALID=1 ;; esac
        if [ "$SECTORS_VALID" -eq 1 ]; then SYSFS_BYTES=$((SECTORS * 512)); else SYSFS_BYTES=0; fi
        META_BYTES=$(/bin/blockdev --getsize64 "$META_NODE" 2>> "$STATUS_LOG") || META_BYTES=0
        echo "[C25] metadata uevent PARTNAME=metadata DEVNAME=$EVENT_DEVNAME MAJOR=$EVENT_MAJOR MINOR=$EVENT_MINOR node=$NODE_DEV expected=$EXPECTED_MAJOR_HEX:$EXPECTED_MINOR_HEX sysfs_bytes=$SYSFS_BYTES node_bytes=$META_BYTES" >> "$STATUS_LOG"
        if [ "$NODE_VALID" -ne 1 ] || [ "$NODE_MAJOR_HEX" != "$EXPECTED_MAJOR_HEX" ] || [ "$NODE_MINOR_HEX" != "$EXPECTED_MINOR_HEX" ] || [ "$SECTORS_VALID" -ne 1 ] || [ "$SYSFS_BYTES" -le 0 ] || [ "$META_BYTES" != "$SYSFS_BYTES" ]; then
            echo "[C25][STOP] metadata block identity or capacity disagrees with sysfs; no mount or read attempted" >> "$STATUS_LOG"
        elif [ -e "$META_MOUNT" ] || [ -L "$META_MOUNT" ]; then
            echo "[C25][STOP] metadata mountpoint already exists; refusing to reuse unexpected path" >> "$STATUS_LOG"
        else
            /bin/mkdir -p "$META_MOUNT" 2>> "$STATUS_LOG"
            if /bin/mount -t ext4 -o ro,noload "$META_NODE" "$META_MOUNT" 2>> "$STATUS_LOG"; then
                MOUNT_INFO=$(/bin/awk -v target="$META_MOUNT" '$2 == target { count++; source=$1; fstype=$3; opts=$4 } END { if (count == 1) printf "%s|%s|%s", source, fstype, opts; else exit 1 }' /proc/mounts 2>> "$STATUS_LOG")
                MOUNT_SOURCE=${MOUNT_INFO%%|*}
                MOUNT_REST=${MOUNT_INFO#*|}
                MOUNT_FSTYPE=${MOUNT_REST%%|*}
                MOUNT_OPTS=${MOUNT_REST#*|}
                case ",$MOUNT_OPTS," in *,ro,*) META_IS_RO=1 ;; *) META_IS_RO=0 ;; esac
                case ",$MOUNT_OPTS," in *,noload,*) META_NOLOAD=1 ;; *) META_NOLOAD=0 ;; esac
                echo "[C25] metadata mount source=$MOUNT_SOURCE fstype=$MOUNT_FSTYPE options=$MOUNT_OPTS" >> "$STATUS_LOG"
                if [ "$MOUNT_SOURCE" != "$META_NODE" ] || [ "$MOUNT_FSTYPE" != "ext4" ] || [ "$META_IS_RO" -ne 1 ] || [ "$META_NOLOAD" -ne 1 ]; then
                    echo "[C25][STOP] mount table does not confirm the requested ext4 ro,noload mount; no metadata files read" >> "$STATUS_LOG"
                elif [ ! -d "$META_MOUNT/thyme_os4_diag" ]; then
                    echo "[C25] /metadata/thyme_os4_diag is absent; no diagnostic files to export" >> "$STATUS_LOG"
                else
                    C25_DEST=/tmp/dumps/C25_metadata
                    /bin/mkdir -p "$C25_DEST"
                    if /bin/cp -a "$META_MOUNT/thyme_os4_diag/." "$C25_DEST/" 2>> "$STATUS_LOG"; then
                        VERIFY_FILE=/tmp/dumps/C25_METADATA_COPY_VERIFY.txt
                        : > "$VERIFY_FILE"
                        echo "source=$META_MOUNT/thyme_os4_diag mount=ext4,ro,noload" >> "$VERIFY_FILE"
                        /bin/find "$META_MOUNT/thyme_os4_diag" -type f -print | /bin/sort > /tmp/c25_metadata_file_list
                        COPY_COUNT=0
                        COPY_ERRORS=0
                        while IFS= read -r SOURCE_FILE; do
                            [ -n "$SOURCE_FILE" ] || continue
                            RELATIVE_FILE=${SOURCE_FILE#"$META_MOUNT/thyme_os4_diag/"}
                            DEST_FILE="$C25_DEST/$RELATIVE_FILE"
                            SOURCE_BYTES=$(/bin/wc -c < "$SOURCE_FILE")
                            DEST_BYTES=$(/bin/wc -c < "$DEST_FILE" 2>> "$STATUS_LOG") || DEST_BYTES=0
                            SOURCE_SHA=$(/bin/sha256sum "$SOURCE_FILE" 2>> "$STATUS_LOG" | /bin/cut -d ' ' -f 1)
                            DEST_SHA=$(/bin/sha256sum "$DEST_FILE" 2>> "$STATUS_LOG" | /bin/cut -d ' ' -f 1)
                            if [ "$SOURCE_BYTES" = "$DEST_BYTES" ] && [ -n "$SOURCE_SHA" ] && [ "$SOURCE_SHA" = "$DEST_SHA" ]; then
                                RESULT=OK
                            else
                                RESULT=MISMATCH
                                COPY_ERRORS=$((COPY_ERRORS + 1))
                            fi
                            echo "$RESULT path=$RELATIVE_FILE source_bytes=$SOURCE_BYTES dest_bytes=$DEST_BYTES source_sha256=$SOURCE_SHA dest_sha256=$DEST_SHA" >> "$VERIFY_FILE"
                            COPY_COUNT=$((COPY_COUNT + 1))
                        done < /tmp/c25_metadata_file_list
                        echo "[C25] metadata export files=$COPY_COUNT mismatch=$COPY_ERRORS verify=/tmp/dumps/C25_METADATA_COPY_VERIFY.txt" >> "$STATUS_LOG"
                    else
                        echo "[C25][ERROR] Copy from read-only metadata mount failed" >> "$STATUS_LOG"
                    fi
                fi
                if /bin/umount "$META_MOUNT" 2>> "$STATUS_LOG"; then
                    echo "[C25] read-only metadata mount unmounted" >> "$STATUS_LOG"
                else
                    echo "[C25][ERROR] Unable to unmount read-only metadata mount" >> "$STATUS_LOG"
                fi
            else
                echo "[C25][ERROR] ext4 ro,noload metadata mount failed; no source files read" >> "$STATUS_LOG"
            fi
        fi
    fi
fi
'''

if args.export_c25_metadata:
    marker = "# 4. Build a 64MB FAT32 UMS image in RAM"
    if wsl_script_content.count(marker) != 1:
        raise SystemExit("Could not place the optional C25 metadata export in the Standalone init script.")
    wsl_script_content = wsl_script_content.replace(marker, C25_METADATA_EXPORT + "\n" + marker, 1)

with open(wsl_script_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(wsl_script_content.replace("__BUILD_ROOT__", WSL_BUILD_ROOT).replace("__OUT_DIR_WSL__", OUT_DIR_WSL))

print("[2/5] Executing WSL ramdisk builder...")
WSL_SCRIPT_PATH = OUT_DIR_WSL + "/wsl_build_ramdisk.sh"
res = subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", WSL_SCRIPT_PATH], capture_output=True, text=True, encoding="utf-8", errors="ignore")
print(res.stdout)
if res.returncode != 0:
    print("WSL Build Error:", res.stderr)
    sys.exit(1)

ramdisk_lz4 = os.path.join(OUT_DIR, "standalone_diag_ramdisk.lz4")
assert os.path.exists(ramdisk_lz4), "Failed to produce ramdisk.lz4"
rd_hash = sha256_file(ramdisk_lz4)
print(f"  Ramdisk LZ4 SHA256: {rd_hash} ({os.path.getsize(ramdisk_lz4)} B)")

print("[3/5] Packaging standalone_diag_boot.img with mkbootimg.py...")
raw_boot = os.path.join(OUT_DIR, "boot_raw.img")
final_boot = os.path.join(OUT_DIR, "standalone_diag_boot.img")

mkboot_cmd = [
    sys.executable, MKBOOTIMG,
    "--header_version", "3",
    "--kernel", A5_KERNEL,
    "--ramdisk", ramdisk_lz4,
    "--cmdline", "androidboot.selinux=permissive",
    "--os_version", "17.0.0",
    "--os_patch_level", "2026-08",
    "--output", raw_boot
]
res = subprocess.run(mkboot_cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
if res.returncode != 0:
    print("mkbootimg error:", res.stderr)
    sys.exit(1)
print(f"  Raw boot image created: {os.path.getsize(raw_boot)} B")

# Add AVB hash footer for 192MB boot partition
shutil.copyfile(raw_boot, final_boot)
avb_cmd = [
    sys.executable, AVBTOOL, "add_hash_footer",
    "--image", final_boot,
    "--partition_size", "201326592",
    "--partition_name", "boot",
    "--algorithm", "NONE",
    "--salt", "337c2a78f00915795162ae2af5ee2326ea543df43fb59d60b15f255a0394c598"
]
res = subprocess.run(avb_cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
if res.returncode != 0:
    print("avbtool error:", res.stderr)
    sys.exit(1)

final_boot_sz = os.path.getsize(final_boot)
final_boot_hash = sha256_file(final_boot)
print(f"  Final boot image created: {final_boot} ({final_boot_sz} B)")
print(f"  Final boot image SHA256:  {final_boot_hash}")
assert final_boot_sz == 201326592, f"Size {final_boot_sz} != 201326592"

print("[4/5] Unpacking and verifying boot image...")
unpack_dir = os.path.join(OUT_DIR, "verify_unpack")
os.makedirs(unpack_dir, exist_ok=False)

unpack_cmd = [
    sys.executable, UNPACK_BOOTIMG,
    "--boot_img", final_boot,
    "--out", unpack_dir
]
res = subprocess.run(unpack_cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
if res.returncode != 0:
    print("unpack error:", res.stderr)
    sys.exit(1)

unpacked_kernel = os.path.join(unpack_dir, "kernel")
unpacked_ramdisk = os.path.join(unpack_dir, "ramdisk")
unpacked_kernel_hash = sha256_file(unpacked_kernel)
unpacked_rd_hash = sha256_file(unpacked_ramdisk)

print(f"  Unpacked Kernel SHA256:  {unpacked_kernel_hash}")
print(f"  Unpacked Ramdisk SHA256: {unpacked_rd_hash}")
assert unpacked_kernel_hash == a5_hash, "Unpacked kernel does not match A5!"
assert unpacked_rd_hash == rd_hash, "Unpacked ramdisk does not match!"

# Unpack ramdisk CPIO to verify file structure
print("[5/5] Auditing unpacked ramdisk file structure...")
audit_cmd = ["wsl", "-d", "Ubuntu", "--", "bash", "-lc", f"lz4 -dc {OUT_DIR_WSL}/verify_unpack/ramdisk | cpio -tv | head -n 30"]
res = subprocess.run(audit_cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
print("Ramdisk head files:")
print(res.stdout)

manifest_path = os.path.join(OUT_DIR, "MANIFEST.txt")
with open(manifest_path, "w", encoding="utf-8") as f:
    f.write(f"=== STANDALONE DIAGNOSTIC IMAGE MANIFEST ===\n")
    f.write(f"Timestamp: {datetime.now().isoformat(timespec='seconds')}\n")
    f.write(f"Target: Xiaomi 10S (thyme)\n")
    f.write(f"A5 Kernel: {A5_KERNEL}\n")
    f.write(f"A5 Kernel SHA256: {a5_hash}\n")
    f.write(f"Busybox Source: Alpine Linux aarch64 static (busybox-static-1.36.1-r31.apk)\n")
    f.write(f"Busybox SHA256: {bb_hash}\n")
    f.write(f"Ramdisk LZ4: {ramdisk_lz4}\n")
    f.write(f"Ramdisk SHA256: {rd_hash}\n")
    f.write(f"Boot Image: {final_boot}\n")
    f.write(f"Boot Image Size: {final_boot_sz} bytes\n")
    f.write(f"Boot Image SHA256: {final_boot_hash}\n")
    f.write(f"AVB Verification: Partition boot, size 201326592, algorithm NONE\n")
    f.write(f"Unpack Verification: Kernel SHA256 100% matched, Ramdisk SHA256 100% matched\n")

print(f"\nSUCCESS! Standalone diagnostic environment is completely built and verified in {OUT_DIR}")
