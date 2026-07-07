# =============================================================================
# RegulaForge - Prometheus with custom config baked in
# =============================================================================

FROM prom/prometheus:v2.51.0

COPY infrastructure/monitoring/prometheus/prometheus.yml /etc/prometheus/prometheus.yml
COPY infrastructure/monitoring/prometheus/alert.rules.yml /etc/prometheus/alert.rules.yml

EXPOSE 9090

USER nobody

ENTRYPOINT ["/bin/prometheus"]
CMD ["--config.file=/etc/prometheus/prometheus.yml", \
     "--storage.tsdb.path=/prometheus", \
     "--storage.tsdb.retention.time=30d", \
     "--web.console.libraries=/usr/share/prometheus/console_libraries", \
     "--web.console.templates=/usr/share/prometheus/consoles", \
     "--web.enable-lifecycle"]
