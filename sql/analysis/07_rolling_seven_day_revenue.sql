-- Rolling seven-day net revenue. mart_daily_revenue contains every calendar day, so a
-- row-based window equals a seven-calendar-day window.
select
    revenue_date,
    net_revenue_amount,
    sum(net_revenue_amount) over seven_days as rolling_7d_net_revenue,
    round(avg(net_revenue_amount) over seven_days, 2) as rolling_7d_avg_daily_net_revenue,
    count(*) over seven_days as days_in_window
from marts.mart_daily_revenue
window seven_days as (order by revenue_date rows between 6 preceding and current row)
order by revenue_date;
