-- Failed or still-running pipeline runs with the stage and error that stopped them,
-- plus any failed data quality checks recorded for the run.
select
    runs.run_id,
    runs.status as run_status,
    stage_runs.stage,
    stage_runs.status as stage_status,
    stage_runs.attempt,
    stage_runs.started_at,
    stage_runs.error_message,
    (
        select count(*)
        from audit.data_quality_results as quality_results
        where quality_results.run_id = runs.run_id and quality_results.status = 'failed'
    ) as failed_quality_checks
from audit.pipeline_runs as runs
inner join audit.pipeline_stage_runs as stage_runs
    on runs.run_id = stage_runs.run_id
where runs.status != 'succeeded'
order by runs.started_at desc, stage_runs.started_at asc;
