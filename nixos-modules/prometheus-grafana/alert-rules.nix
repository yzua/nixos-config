# Prometheus alerting rules for system health monitoring.

[
  ''
    groups:
      - name: system
        rules:
          - alert: HighCpuLoad
            expr: netdata_system_cpu_percentage_average{dimension="idle"} < 10
            for: 5m
            labels:
              severity: warning
            annotations:
              summary: "High CPU usage on {{ $labels.instance }}"
              description: "CPU idle below 10% for 5 minutes (current: {{ $value | printf \"%.1f\" }}%)"

          - alert: HighMemoryUsage
            expr: netdata_system_ram_MiB_average{dimension="free"} + netdata_system_ram_MiB_average{dimension="cached"} + netdata_system_ram_MiB_average{dimension="buffers"} < 512
            for: 5m
            labels:
              severity: warning
            annotations:
              summary: "High memory usage on {{ $labels.instance }}"
              description: "Less than 512MB available RAM for 5 minutes"

          - alert: CriticalMemoryUsage
            expr: netdata_system_ram_MiB_average{dimension="free"} + netdata_system_ram_MiB_average{dimension="cached"} + netdata_system_ram_MiB_average{dimension="buffers"} < 256
            for: 2m
            labels:
              severity: critical
            annotations:
              summary: "Critical memory usage on {{ $labels.instance }}"
              description: "Less than 256MB available RAM for 2 minutes — earlyoom may trigger"

          - alert: HighSystemLoad
            expr: netdata_system_load_load_average{dimension="load15"} > 8
            for: 10m
            labels:
              severity: warning
            annotations:
              summary: "High system load on {{ $labels.instance }}"
              description: "15-minute load average above 8 for 10 minutes (current: {{ $value | printf \"%.1f\" }})"

      - name: disk
        rules:
          - alert: DiskSpaceWarning
            expr: netdata_disk_space_GiB_average{dimension="avail"} / (netdata_disk_space_GiB_average{dimension="avail"} + netdata_disk_space_GiB_average{dimension="used"}) * 100 < 15
            for: 5m
            labels:
              severity: warning
            annotations:
              summary: "Disk space low on {{ $labels.instance }} ({{ $labels.family }})"
              description: "Less than 15% disk space remaining for 5 minutes"

          - alert: DiskSpaceCritical
            expr: netdata_disk_space_GiB_average{dimension="avail"} / (netdata_disk_space_GiB_average{dimension="avail"} + netdata_disk_space_GiB_average{dimension="used"}) * 100 < 5
            for: 2m
            labels:
              severity: critical
            annotations:
              summary: "Disk space critical on {{ $labels.instance }} ({{ $labels.family }})"
              description: "Less than 5% disk space remaining"

      - name: services
        rules:
          - alert: SystemdServiceFailed
            expr: netdata_systemd_units_units_state_average{dimension="failed"} > 0
            for: 5m
            labels:
              severity: critical
            annotations:
              summary: "Systemd service failure on {{ $labels.instance }}"
              description: "One or more systemd units in failed state for 5 minutes"

          - alert: PrometheusTargetDown
            expr: up == 0
            for: 10m
            labels:
              severity: warning
            annotations:
              summary: "Scrape target down: {{ $labels.job }} on {{ $labels.instance }}"
              description: "Prometheus cannot reach {{ $labels.job }} for 15 minutes"

      - name: network
        rules:
          - alert: HighNetworkErrors
            expr: rate(netdata_net_errors_errors_persec_average[5m]) > 10
            for: 5m
            labels:
              severity: warning
            annotations:
              summary: "Network errors on {{ $labels.instance }} ({{ $labels.family }})"
              description: "More than 10 network errors/sec for 5 minutes"
  ''
]
