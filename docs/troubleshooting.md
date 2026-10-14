# Troubleshooting

## Diagnosing a failed run

1. **Find the failed stage.** In Airflow, the red task in the grid view is the failing stage, and
   its log contains the error from the `dataforge` CLI. In the database, run
   `sql/diagnostics/pipeline_run_failures.sql`. Example output from a local run that exceeded the
   quarantine threshold:

   ```text
    run_id                  | run_status | stage           | stage_status | attempt | error_message
   -------------------------+------------+-----------------+--------------+---------+-------------------------------------------------
    manual__threshold_check | failed     | validate_source | failed       |       1 | RuntimeError: Blocking validation failures: products.rejected_ratio_within_thres...
   ```

2. **Read the data quality report** for the run in `data/reports/<run_id>/data_quality_report.md`,
   or query `audit.data_quality_results` filtered by `run_id` and `status = 'failed'`.
3. **Trace rows back to the file.** Run `sql/diagnostics/quarantined_records.sql`. It lists each
   quarantined row's `_source_file`, `_source_line`, and `_rejection_reasons`.
4. **Fix and rerun.** Correct the extract or the code, then clear the failed task in Airflow (or
   rerun the CLI with the same `--run-id`). The batch is replaced, not duplicated.

## Common problems

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Configuration error: Missing required database settings: DATAFORGE_DB_PASSWORD...` | Environment not loaded. | `make env`, edit `.env`, and run commands through `make` (it loads `.env`). Alternatively `set -a; source .env; set +a`. |
| `required variable DATAFORGE_DB_USER is missing a value` from Docker Compose | No `.env` file next to `docker-compose.yml`. | `make env` and set the placeholders. |
| `connection refused` on port 5433 | PostgreSQL container not running, or a different port in `.env`. | `make db-up`, then `make ps`. Host-side commands use `DATAFORGE_DB_PORT` (default 5433, so it does not collide with a local PostgreSQL on 5432). |
| Port 8080 already in use | Another service holds the Airflow UI port. | Set `AIRFLOW_HOST_PORT` in `.env`. |
| `validate_source_files` fails with `rejected_ratio_within_threshold` | Too many rows were quarantined; the extract is probably broken. | Inspect the quarantined rows. If the volume is expected, raise `DATAFORGE_MAX_REJECTED_RATIO` deliberately. |
| `validate_source_files` fails with `required_columns_present` | The source schema changed. | Align the extract with `src/dataforge/contracts.py`, or evolve the contract together with the dbt staging model. |
| `check_source_availability` fails with `Missing source files` | No files in `DATAFORGE_SOURCE_DIR`, and `generate_if_missing` is false. | Deliver the files, or trigger with `{"generate_if_missing": true}`. |
| `dbt_run` fails with `relation "reference.order_statuses" does not exist` | dbt models ran before the seed. | Run `dbt seed` first; the DAG and `run-pipeline` already do this. |
| `dbt_test` fails | A data test with error severity failed. | The task log names the test. Its failing rows can be inspected with `dbt test --select <test> --store-failures` from the project directory. |
| `run_quality_checks` fails on `staging_row_count_matches_raw` | Staging dropped or duplicated keys, for example after a manual edit of raw tables. | Compare `raw.<entity>` valid keys with the staging view. Rerun the batch. |
| Airflow tasks stay `queued` | `max_active_runs=1` and another run is active, or the scheduler is unhealthy. | Check the DAG's runs in the UI and `make ps`. |
| DAG shows an import error | Syntax or import problem in `dags/`. | `docker compose --profile airflow exec airflow-scheduler airflow dags list-import-errors`. Locally: `make test-dag`. |
| Airflow containers restart or are killed | Docker has too little memory. | Give the Docker VM or host at least 4 GB. A local run of this stack used roughly 1 GB across its containers. |
| Files in `data/` are owned by an unknown user on Linux | Containers run as `AIRFLOW_UID`. | Set `AIRFLOW_UID=$(id -u)` in `.env` before `make up`. |
| Schema changes in the raw or audit tables do not appear | `init-db` only creates missing tables. | Development: `make reset` drops all volumes and data. |

## Inspecting the environment

```bash
make ps                           # container status and health
make logs                         # follow all service logs
make psql                         # SQL shell on the warehouse database
docker compose --profile airflow exec airflow-scheduler airflow dags list-runs marketplace_pipeline
docker compose --profile airflow exec airflow-scheduler airflow tasks states-for-dag-run marketplace_pipeline <run_id>
```
