-- Daily and monthly revenue trend (UTC order date, revenue-eligible orders only).
-- gross_sales = sum(quantity * unit_price)
-- net_sales   = gross_sales - discounts
-- net_revenue = net_sales - refunds
select
    'day' as grain,
    revenue_date as period_start,
    revenue_orders,
    gross_sales_amount,
    discount_amount,
    net_sales_amount,
    refunded_amount,
    net_revenue_amount
from marts.mart_daily_revenue

union all

select
    'month' as grain,
    date_trunc('month', revenue_date)::date as period_start,
    sum(revenue_orders) as revenue_orders,
    sum(gross_sales_amount) as gross_sales_amount,
    sum(discount_amount) as discount_amount,
    sum(net_sales_amount) as net_sales_amount,
    sum(refunded_amount) as refunded_amount,
    sum(net_revenue_amount) as net_revenue_amount
from marts.mart_daily_revenue
group by date_trunc('month', revenue_date)

order by grain, period_start;
