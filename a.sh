set -x
now=$(date +%s)
            threshold=$((60*60*24))  # 24時間

            for net in $(docker network ls --format '{{.Name}}'); do
                if [[ "$net" == "bridge" || "$net" == "host" || "$net" == "none" ]]; then
                    continue
                fi

                attached=$(docker network inspect "$net" --format '{{json .Containers}}')
                if [[ "$attached" != "{}" ]]; then
                    continue
                fi

                created=$(docker network inspect "$net" --format '{{.Created}}')
                created_fixed=$(echo "$created" | sed -E 's/\.[0-9]+//; s/ [A-Z]+$//')
                created_ts=$(date --date="$created_fixed" +%s)

                if [[ -n "$created_ts" && $((now - created_ts)) -gt $threshold ]]; then
                    echo "Removing unused network: $net (created at $created)"
                    docker network rm "$net" || true
                fi
            done
