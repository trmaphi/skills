#!/usr/bin/env bash
set -euo pipefail

fps=${TIMELAPSE_FPS:-30}
root=${TIMELAPSE_ROOT:-${HOME}/Pictures/TIMELAPSE}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

for tool in dcraw cjpeg ffmpeg ffprobe; do
  command -v "$tool" >/dev/null 2>&1 || die "missing required tool: $tool"
done

case "$fps" in
  ''|*[!0-9]*) die "TIMELAPSE_FPS must be a positive integer" ;;
  0) die "TIMELAPSE_FPS must be greater than zero" ;;
esac

source_dir=${1:-}
if [ -z "$source_dir" ]; then
  [ -d "$root" ] || die "timelapse root not found: $root"
  while IFS= read -r candidate; do
    name=$(basename "$candidate")
    exact="$root/$name.mp4"
    legacy="$root/timelapse_${name}_30fps.mp4"
    if find "$candidate" -maxdepth 1 -type f -name 'TIMELAPSE_[0-9][0-9][0-9][0-9].DNG' -print -quit | grep -q . \
      && [ ! -e "$exact" ] && [ ! -e "$legacy" ]; then
      source_dir=$candidate
      break
    fi
  done < <(find "$root" -mindepth 1 -maxdepth 1 -type d -print | sort)
  [ -n "$source_dir" ] || die "no unrendered DJI Action timelapse folder found under $root"
fi

[ -d "$source_dir" ] || die "source folder not found: $source_dir"
source_dir=$(cd "$source_dir" && pwd -P)
name=$(basename "$source_dir")
output="$(dirname "$source_dir")/$name.mp4"
[ ! -e "$output" ] || die "output already exists: $output"
legacy_output="$(dirname "$source_dir")/timelapse_${name}_30fps.mp4"
[ ! -e "$legacy_output" ] || die "legacy output already exists: $legacy_output"

lock_dir="$output.lock"
mkdir "$lock_dir" 2>/dev/null || die "another render is active or left a lock: $lock_dir"
work_dir=''
trap 'if [ -n "$work_dir" ]; then rm -rf "$work_dir"; fi; rm -rf "$lock_dir"' EXIT INT TERM
work_dir=$(mktemp -d "$(dirname "$output")/.dji-action-timelapse.XXXXXX")
trap 'rm -rf "$work_dir" "$lock_dir"' EXIT INT TERM
frames_dir="$work_dir/frames"
mkdir -p "$frames_dir"

frame_count=$(find "$source_dir" -maxdepth 1 -type f -name 'TIMELAPSE_[0-9][0-9][0-9][0-9].DNG' | wc -l | tr -d ' ')
[ "$frame_count" -gt 0 ] || die "no DJI Action TIMELAPSE_####.DNG files found"
all_dng_count=$(find "$source_dir" -maxdepth 1 -type f -iname '*.DNG' | wc -l | tr -d ' ')
[ "$all_dng_count" -eq "$frame_count" ] || die "folder contains malformed or non-DJI DNG filenames"

i=1
while [ "$i" -le "$frame_count" ]; do
  printf -v number '%04d' "$i"
  [ -f "$source_dir/TIMELAPSE_${number}.DNG" ] || die "sequence is not contiguous; missing TIMELAPSE_${number}.DNG"
  i=$((i + 1))
done

export source_dir frames_dir
seq 1 "$frame_count" | xargs -P 8 -I{} bash -c '
  set -eu
  set -o pipefail
  number=$(printf "%04d" "$1")
  dcraw -c -w -q 3 -H 2 "$source_dir/TIMELAPSE_${number}.DNG" |
    cjpeg -quality 92 -outfile "$frames_dir/frame_${number}.jpg"
' _ {}

exported=$(find "$frames_dir" -maxdepth 1 -type f -name 'frame_*.jpg' | wc -l | tr -d ' ')
[ "$exported" -eq "$frame_count" ] || die "expected $frame_count developed frames, found $exported"

temporary_output="$work_dir/$name.mp4"
ffmpeg -hide_banner -y \
  -framerate "$fps" -start_number 1 -i "$frames_dir/frame_%04d.jpg" \
  -vf 'scale=trunc(iw/2)*2:trunc(ih/2)*2' \
  -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p \
  -movflags +faststart "$temporary_output"

[ -s "$temporary_output" ] || die "encoder did not produce a video"
probe=$(ffprobe -v error -count_frames -select_streams v:0 \
  -show_entries stream=codec_name,width,height,pix_fmt,r_frame_rate,nb_read_frames:format=duration \
  -of default=noprint_wrappers=1 "$temporary_output")
value() { printf '%s\n' "$probe" | awk -F= -v key="$1" '$1 == key { print $2 }'; }
video_frames=$(value nb_read_frames)
[ "$video_frames" = "$frame_count" ] || die "video has $video_frames frames; expected $frame_count"
codec=$(value codec_name)
[ "$codec" = h264 ] || die "unexpected codec: $codec"
pixel_format=$(value pix_fmt)
case "$pixel_format" in yuv420p|yuvj420p) ;; *) die "unexpected pixel format: $pixel_format" ;; esac
rate=$(value r_frame_rate)
[ "$rate" = "$fps/1" ] || die "video frame rate is $rate; expected $fps/1"
width=$(value width)
height=$(value height)
[ $((width % 2)) -eq 0 ] && [ $((height % 2)) -eq 0 ] || die "video dimensions must be even: ${width}x${height}"
duration=$(value duration)
awk -v actual="$duration" -v frames="$frame_count" -v rate="$fps" 'BEGIN { expected=frames/rate; delta=actual-expected; if (delta<0) delta=-delta; exit(delta <= 0.05 ? 0 : 1) }' \
  || die "video duration is $duration; expected approximately $(awk -v n="$frame_count" -v r="$fps" 'BEGIN { print n/r }')"
ffmpeg -v error -i "$temporary_output" -f null -

[ ! -e "$output" ] || die "output appeared during rendering: $output"
mv -n "$temporary_output" "$output"
[ -s "$output" ] && [ ! -e "$temporary_output" ] || die "atomic publication failed"
printf 'Created: %s\n%s\n' "$output" "$probe"
