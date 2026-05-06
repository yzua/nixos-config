#!/usr/bin/env bash
# Security collectors for system report generation.

collect_security() {
	section "Security"

	local items=()

	if [[ "$HAS_FAIL2BAN" == "true" ]] && command -v fail2ban-client &>/dev/null; then
		local fail2ban_status
		fail2ban_status=$(safe_cmd fail2ban-client status 2>/dev/null)
		if [[ -z "$fail2ban_status" ]]; then
			items+=("- fail2ban: [unavailable]")
			_FAIL2BAN_BANNED="0"
		else
			local jail_list jail banned total_bans total_banned_now total_banned_ever
			jail_list=$(echo "$fail2ban_status" | awk -F: '/Jail list:/ {gsub(/^[[:space:]]+/, "", $2); print $2}' | tr ',' ' ')
			if [[ -z "$jail_list" ]]; then
				items+=("- fail2ban: 0 currently banned, 0 total bans (no active jails)")
				_FAIL2BAN_BANNED="0"
			else
				total_banned_now=0
				total_banned_ever=0
				for jail in $jail_list; do
					local jail_status
					jail_status=$(safe_cmd fail2ban-client status "$jail" 2>/dev/null || true)
					banned=$(echo "$jail_status" | awk -F: '/Currently banned:/ {gsub(/^[[:space:]]+/, "", $2); print $2}')
					total_bans=$(echo "$jail_status" | awk -F: '/Total banned:/ {gsub(/^[[:space:]]+/, "", $2); print $2}')
					banned="${banned:-0}"
					total_bans="${total_bans:-0}"
					[[ "$banned" =~ ^[0-9]+$ ]] || banned=0
					[[ "$total_bans" =~ ^[0-9]+$ ]] || total_bans=0
					total_banned_now=$((total_banned_now + banned))
					total_banned_ever=$((total_banned_ever + total_bans))
				done
				items+=("- fail2ban: ${total_banned_now} currently banned, ${total_banned_ever} total bans (${jail_list})")
				_FAIL2BAN_BANNED="${total_banned_now}"
			fi
		fi
	else
		items+=("- fail2ban: [unavailable]")
		_FAIL2BAN_BANNED="0"
	fi

	local lynis_output
	lynis_output=$(safe_cmd journalctl -u security-audit --no-pager -n 50 --since "-7d" 2>/dev/null)
	if [[ -n "$lynis_output" ]]; then
		local score
		score=$(echo "$lynis_output" | grep -oP 'Hardening index : \K[0-9]+' | tail -1 || echo "")
		if [[ -n "$score" ]]; then
			items+=("- Lynis audit score: ${score}/100")
		else
			items+=("- Lynis: no recent audit score found")
		fi
	else
		items+=("- Lynis: [unavailable]")
	fi

	if [[ "$HAS_OPENSNITCH" == "true" ]]; then
		local blocked
		blocked=$(safe_cmd journalctl -u opensnitchd --no-pager --since "-24h" -o json 2>/dev/null |
			jq -rs '[.[] | select(.MESSAGE? | test("blocked"; "i"))] | length' 2>/dev/null || echo "0")
		items+=("- OpenSnitch: ${blocked:-0} blocked connections (24h)")
	else
		items+=("- OpenSnitch: [unavailable]")
	fi

	if command -v systemd-analyze &>/dev/null; then
		local exposed
		exposed=$(safe_cmd systemd-analyze security --no-pager 2>/dev/null |
			awk '$NF == "EXPOSED" || $NF == "UNSAFE" {count++} END {print count+0}') || exposed="0"
		items+=("- systemd unit hardening: ${exposed} units rated EXPOSED/UNSAFE")
	fi

	if [[ "$HAS_SECURE_BOOT" == "true" ]] && command -v mokutil &>/dev/null && command -v sbctl &>/dev/null; then
		local sb_state sb_status unsigned_count
		sb_state=$(safe_cmd mokutil --sb-state 2>/dev/null)
		sb_status=$(safe_cmd sbctl status 2>/dev/null)
		unsigned_count=$(safe_cmd sbctl verify 2>/dev/null | awk '/failed|unsigned/ {count++} END {print count+0}')
		if echo "$sb_state" | grep -qi 'SecureBoot enabled'; then
			items+=("- Secure Boot: enabled, ${unsigned_count:-0} unsigned or failed sbctl entries")
		else
			local setup_mode
			setup_mode=$(echo "$sb_status" | awk -F: '/Setup Mode:/ {gsub(/^[[:space:]]+/, "", $2); print $2}' | head -1)
			items+=("- Secure Boot: not enabled (${setup_mode:-firmware state unknown})")
		fi
	else
		items+=("- Secure Boot: [unavailable]")
	fi

	printf '%s\n' "${items[@]}"
}
