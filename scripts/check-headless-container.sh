#!/usr/bin/env bash
set -euo pipefail

readonly image="scrap-monitoring-lidar-visualizer:p1"
probe_root="$(mktemp -d)"
readonly probe_root

cleanup() {
  docker run --rm \
    --network none \
    --entrypoint chmod \
    --mount "type=bind,source=${probe_root}/output,target=/output" \
    "${image}" -R a+rwX /output >/dev/null 2>&1 || true
  rm -rf -- "${probe_root}"
}

trap cleanup EXIT

install -d -m 0777 "${probe_root}/output"

docker build --platform linux/amd64 --tag "${image}" .

readonly -a runtime_options=(
  --rm
  --platform linux/amd64
  --network none
  --read-only
  --cap-drop ALL
  --security-opt no-new-privileges
  --pids-limit 128
  --memory 1g
  --cpus 2
  --tmpfs /tmp:rw,noexec,nosuid,size=64m
)

docker run "${runtime_options[@]}" \
  --mount "type=bind,source=${probe_root}/output,target=/output" \
  "${image}"

docker run "${runtime_options[@]}" \
  --mount "type=bind,source=${probe_root}/output,target=/output" \
  --entrypoint python \
  "${image}" \
  -m scrap_monitoring_lidar_visualizer.rendering.probe \
  --output /output/scene

test "$(jq -r '.display_present' "${probe_root}/output/probe/probe.json")" = "false"
test "$(jq -r '.euid' "${probe_root}/output/probe/probe.json")" = "10001"
test "$(jq -r '.gpu_device_present' "${probe_root}/output/probe/probe.json")" = "false"
test "$(jq -r '.render_window' "${probe_root}/output/probe/probe.json")" = "vtkOSOpenGLRenderWindow"
test "$(jq -r '.frame_count' "${probe_root}/output/probe/probe.json")" = "10"
test "$(jq -r '.width' "${probe_root}/output/probe/probe.json")" = "640"
test "$(jq -r '.height' "${probe_root}/output/probe/probe.json")" = "360"
test -s "${probe_root}/output/probe/frame.png"
test -s "${probe_root}/output/probe/probe.mp4"
test "$(jq -r '.display_present' "${probe_root}/output/scene/scene.json")" = "false"
test "$(jq -r '.euid' "${probe_root}/output/scene/scene.json")" = "10001"
test "$(jq -r '.render_window' "${probe_root}/output/scene/scene.json")" = "vtkOSOpenGLRenderWindow"
test "$(jq -r '.width' "${probe_root}/output/scene/scene.json")" = "640"
test "$(jq -r '.height' "${probe_root}/output/scene/scene.json")" = "360"
test "$(jq -r '.surface_faces > 0' "${probe_root}/output/scene/scene.json")" = "true"
test -s "${probe_root}/output/scene/scene.png"
test -s "${probe_root}/output/scene/scene-top.png"

benchmark_json="$(
  docker run "${runtime_options[@]}" \
    "${image}" \
    --output /tmp/benchmark \
    --frame-count 1 \
    --grid-x 512 \
    --grid-y 512
)"
readonly benchmark_json
test "$(jq -r '.grid_points' <<<"${benchmark_json}")" = "262144"
printf '%s\n' "${benchmark_json}"

docker run "${runtime_options[@]}" \
  --mount "type=bind,source=${probe_root}/output,target=/output,readonly" \
  --entrypoint ffprobe \
  "${image}" \
  -v error \
  -select_streams v:0 \
  -show_entries stream=codec_name,width,height \
  -of default=noprint_wrappers=1 \
  /output/probe/probe.mp4
