#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
app_dir="$project_dir/SilentAgent.app"

cd "$project_dir"
swift build -c release
mkdir -p "$app_dir/Contents/MacOS"
cp "$project_dir/.build/release/silent-agent" "$app_dir/Contents/MacOS/silent-agent"
cp "$project_dir/AppBundle/Info.plist" "$app_dir/Contents/Info.plist"
codesign --force --sign - --identifier com.harishangadala.silentagent "$app_dir"
echo "Built $app_dir"
