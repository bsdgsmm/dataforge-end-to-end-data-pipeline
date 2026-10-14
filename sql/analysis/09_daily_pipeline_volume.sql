-- Records and customers processed per pipeline run (operational volume, not sales).
select
    runs.run_id,
    runs.status,
    runs.started_at,
    runs.finished_at,
    sum(stats.rows_received) filter (where stats.entity = 'orders') as orders_received,
    sum(stats.rows_rejected) filter (where stats.entity = 'orders') as orders_quarantined,
    sum(stats.rows_received) filter (where stats.entity = 'customers') as customers_received,
    sum(stats.rows_received) as total_rows_received,
    sum(stats.rows_rejected) as total_rows_quarantined
from audit.pipeline_runs as runs
left join audit.raw_load_stats as stats
    on runs.run_id = stats.run_id
group by runs.run_id, runs.status, runs.started_at, runs.finished_at
order by runs.started_at desc;
