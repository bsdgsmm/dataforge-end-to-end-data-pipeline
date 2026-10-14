-- Month-over-month change in net revenue (net sales minus refunds).
with monthly as (
    select
        date_trunc('month', revenue_date)::date as revenue_month,
        sum(net_revenue_amount) as net_revenue_amount
    from marts.mart_daily_revenue
    group by date_trunc('month', revenue_date)
)

select
    revenue_month,
    net_revenue_amount,
    lag(net_revenue_amount) over (order by revenue_month) as previous_month_net_revenue,
    net_revenue_amount
    - lag(net_revenue_amount) over (order by revenue_month) as net_revenue_change,
    round(
        (
            net_revenue_amount
            - lag(net_revenue_amount) over (order by revenue_month)
        )
        / nullif(lag(net_revenue_amount) over (order by revenue_month), 0),
        4
    ) as net_revenue_change_rate
from monthly
order by revenue_month;
