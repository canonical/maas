#!/bin/bash

# Compresses images for intended for docs usage.

if [ -z "$1" ]; then
  echo "Usage: ./compress.sh filename.png"
  exit 1
fi

INPUT="$1"
OUTPUT="${INPUT%.*}.webp"

echo "Compressing $INPUT..."

FFMPEG_OPTS=(
  -vcodec libwebp                              # encode to WebP format
  -lossless 0                                  # use lossy compression for smaller files
  -compression_level 6                         # max compression effort (0-6)
  -preset drawing                              # optimise for screenshots/UI: flat colours and sharp edges
  -q:v 85                                      # quality level (0-100); lower means smaller file
  -map_metadata -1                             # strip all metadata (EXIF, GPS, timestamps, etc.)
  -vf "scale='min(1280,iw)':-1,format=yuv420p" # cap width at 1280px, preserving aspect ratio; pass YUV to encoder
)

ffmpeg -i "$INPUT" "${FFMPEG_OPTS[@]}" "$OUTPUT" -y

if [ -f "$OUTPUT" ]; then
  OLD_SIZE=$(du -h "$INPUT" | cut -f1)
  NEW_SIZE=$(du -h "$OUTPUT" | cut -f1)
  echo "Done! Final size: $NEW_SIZE (Was: $OLD_SIZE)"
else
  echo "Error: Conversion failed."
fi
