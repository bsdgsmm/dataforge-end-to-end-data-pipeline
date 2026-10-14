-- Average order value (AOV) per month: net sales of revenue-eligible orders divided by
-- the number of those orders. Refunds are excluded so AOV reflects basket size at checkout.
select
    date_trunc('month', order_date)::date as order_month,
    count(*) as revenue_orders,
    sum(net_sales_amount) as net_sales_amount,
    round(avg(net_sales_amount), 2) as average_order_value,
    percentile_cont(0.5) within group (order by net_sales_amount) as median_order_value
from marts.fct_orders
where is_revenue_eligible
group by date_trunc('month', order_date)
order by order_month;
