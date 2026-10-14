# Airflow image with the DataForge pipeline and dbt installed in an isolated virtualenv.
# Keeping them out of Airflow's own environment avoids dependency conflicts between
# Airflow, dbt, and the pipeline; DAG tasks call the CLI from the virtualenv.
FROM apache/airflow:3.3.2-python3.12

USER root
RUN mkdir -p /opt/dataforge /opt/dataforge-venv \
    && chown -R airflow:root /opt/dataforge /opt/dataforge-venv
USER airflow

COPY --chown=airflow:root pyproject.toml README.md constraints.txt /opt/dataforge/
COPY --chown=airflow:root src /opt/dataforge/src
RUN python -m venv /opt/dataforge-venv \
    && /opt/dataforge-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/dataforge-venv/bin/pip install --no-cache-dir \
        --constraint /opt/dataforge/constraints.txt "/opt/dataforge[dbt]"

COPY --chown=airflow:root dbt /opt/dataforge/dbt

ENV DATAFORGE_CLI=/opt/dataforge-venv/bin/dataforge \
    DATAFORGE_SOURCE_DIR=/opt/dataforge/data/source \
    DATAFORGE_REPORT_DIR=/opt/dataforge/data/reports \
    DATAFORGE_DBT_PROJECT_DIR=/opt/dataforge/dbt/marketplace_analytics
