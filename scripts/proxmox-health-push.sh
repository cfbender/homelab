#!/usr/bin/env bash
# Proxmox host health checks, each reported to its own Uptime Kuma push monitor
# (group "Proxmox health" at uptime.cfb.dev).
#
# Installed on the Proxmox host as /usr/local/bin/proxmox-health-push and run every
# 5 minutes by proxmox-health-push.timer. Push tokens live in
# /etc/proxmox-health-push.env (mode 600): KUMA_URL and TOKEN_* below.
#
# DRY_RUN=1 proxmox-health-push   prints each result instead of pushing it.

set -uo pipefail
# shellcheck source=/dev/null
. /etc/proxmox-health-push.env

USAGE_MAX=${USAGE_MAX:-85}               # percent used before storage, thin pools, or ZFS alert
BACKUP_MAX_AGE_HOURS=${BACKUP_MAX_AGE_HOURS:-26}
TRUENAS_VMID=${TRUENAS_VMID:-101}
MOUNTS=${MOUNTS:-"/mnt/unas /mnt/pve/backup"}
# Thick LVM storage reports its full allocation as used.
STORAGE_IGNORE_USAGE=${STORAGE_IGNORE_USAGE:-"frigate"}

push() { # token status msg
    if [[ -n ${DRY_RUN:-} ]]; then
        printf '%-5s %s\n' "$2" "$3"
        return
    fi
    curl -fsS -m 15 -o /dev/null -G "$KUMA_URL/api/push/$1" \
        --data-urlencode "status=$2" --data-urlencode "msg=$3" ||
        echo "push failed: $3" >&2
}

report() { # token ok_msg [problem...]
    local token=$1 ok_msg=$2
    shift 2
    if (($#)); then
        local IFS=';'
        push "$token" down "$*"
    else
        push "$token" up "$ok_msg"
    fi
}

json_field() { # key: prints a top-level field (or field of the first element) of JSON on stdin
    perl -MJSON::PP -0777 -e '
        my $d = decode_json(<STDIN>);
        $d = $d->[0] if ref $d eq "ARRAY";
        print $d->{$ARGV[0]} // "";
    ' "$1"
}

check_storage() {
    local problems=() name type status total used avail pct out
    if ! out=$(pvesm status 2>&1); then
        report "$TOKEN_STORAGE" "" "pvesm status failed: $out"
        return
    fi
    while read -r name type status total used avail pct; do
        [[ $status == disabled ]] && continue
        if [[ $status != active ]]; then
            problems+=("$name $status")
            continue
        fi
        [[ " $STORAGE_IGNORE_USAGE " == *" $name "* ]] && continue
        pct=${pct%\%}
        pct=${pct%.*}
        [[ $pct =~ ^[0-9]+$ ]] && ((pct >= USAGE_MAX)) && problems+=("$name ${pct}% used")
    done < <(tail -n +2 <<<"$out")
    report "$TOKEN_STORAGE" "all storage active, under ${USAGE_MAX}%" "${problems[@]}"
}

check_thin_pools() {
    local problems=() vg lv pool data meta out
    if ! out=$(lvs --noheadings --separator ' ' -o vg_name,lv_name,data_percent,metadata_percent \
        -S 'segtype=thin-pool' 2>&1); then
        report "$TOKEN_THIN" "" "lvs failed: $out"
        return
    fi
    while read -r vg lv data meta; do
        pool="$vg/$lv"
        data=${data%.*}
        meta=${meta%.*}
        ((data >= USAGE_MAX)) && problems+=("$pool data ${data}%")
        ((meta >= USAGE_MAX)) && problems+=("$pool metadata ${meta}%")
    done <<<"$out"
    report "$TOKEN_THIN" "thin pools under ${USAGE_MAX}%" "${problems[@]}"
}

truenas_exec() { # command...: prints stdout of a command run in the TrueNAS VM
    local json
    json=$(qm guest exec "$TRUENAS_VMID" --timeout 30 -- "$@" 2>&1) || {
        echo "guest exec on VM $TRUENAS_VMID failed: $json"
        return 1
    }
    json_field out-data <<<"$json"
}

check_zfs() {
    local problems=() list status name health cap
    if ! list=$(truenas_exec zpool list -H -o name,health,cap) ||
        ! status=$(truenas_exec zpool status -x); then
        report "$TOKEN_ZFS" "" "${list:-$status}"
        return
    fi
    while read -r name health cap; do
        [[ -z $name ]] && continue
        [[ $health != ONLINE ]] && problems+=("$name $health")
        cap=${cap%\%}
        ((cap >= USAGE_MAX)) && problems+=("$name ${cap}% used")
    done <<<"$list"
    [[ $status == *'all pools are healthy'* ]] || problems+=("zpool status -x reports problems")
    report "$TOKEN_ZFS" "TrueNAS pools healthy, under ${USAGE_MAX}%" "${problems[@]}"
}

check_smart() {
    local problems=() line args count=0
    while read -r line; do
        read -ra args <<<"${line%%#*}"
        ((${#args[@]})) || continue
        count=$((count + 1))
        smartctl -H "${args[@]}" | grep -qE 'PASSED|: OK' || problems+=("${args[0]} SMART failing")
    done < <(smartctl --scan)
    ((count)) || problems+=("smartctl found no disks")
    report "$TOKEN_SMART" "$count disks PASSED" "${problems[@]}"
}

check_backup() {
    local json status start age
    if ! json=$(pvesh get "/nodes/$(hostname)/tasks" --typefilter vzdump --limit 1 --output-format json 2>&1); then
        report "$TOKEN_BACKUP" "" "pvesh tasks failed: $json"
        return
    fi
    status=$(json_field status <<<"$json")
    start=$(json_field starttime <<<"$json")
    if [[ -z $start ]]; then
        report "$TOKEN_BACKUP" "" "no vzdump task found"
        return
    fi
    age=$((($(date +%s) - start) / 3600))
    local problems=()
    [[ $status != OK ]] && problems+=("last vzdump: $status")
    ((age >= BACKUP_MAX_AGE_HOURS)) && problems+=("last vzdump ${age}h ago")
    report "$TOKEN_BACKUP" "last vzdump OK, ${age}h ago" "${problems[@]}"
}

check_mounts() {
    local problems=() m
    for m in $MOUNTS; do
        findmnt -n "$m" >/dev/null || { problems+=("$m not mounted"); continue; }
        # A hung NFS mount blocks stat; time it out instead of hanging the timer.
        timeout 10 stat -f "$m" >/dev/null 2>&1 || problems+=("$m not responding")
    done
    report "$TOKEN_MOUNTS" "mounted: $MOUNTS" "${problems[@]}"
}

check_systemd() {
    local failed
    failed=$(systemctl --failed --no-legend --plain | awk '{print $1}' | paste -sd' ')
    if [[ -n $failed ]]; then
        report "$TOKEN_SYSTEMD" "" "failed units: $failed"
    else
        report "$TOKEN_SYSTEMD" "no failed units"
    fi
}

check_storage
check_thin_pools
check_zfs
check_smart
check_backup
check_mounts
check_systemd
