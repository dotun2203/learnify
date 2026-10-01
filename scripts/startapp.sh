#!/usr/bin/env bash
# Usage: ./scripts/startapp.sh <app_name>   — creates apps/<app_name> in the project layout
set -euo pipefail
name="$1"
mkdir -p "apps/$name"
python manage.py startapp "$name" "apps/$name"
sed -i "s/name = '$name'/name = 'apps.$name'/; s/name = \"$name\"/name = \"apps.$name\"/" "apps/$name/apps.py"
for f in services selectors tasks; do touch "apps/$name/$f.py"; done
echo "Created apps/$name — now add \"apps.$name\" to LOCAL_APPS in config/settings/base.py"
