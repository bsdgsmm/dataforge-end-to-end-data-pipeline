-- Daily revenue totals must match the order fact for every measure.
with order_totals as (
    select
        count(*) filter (where is_revenue_eligible) as revenue_orders,
        sum(gross_sales_amount) filter (where is_revenue_eligible) as gross_sales_amount,
        sum(refunded_amount) filter (where is_revenue_eligible) as refunded_amount,
        sum(net_revenue_amount) filter (where is_revenue_eligible) as net_revenue_amount
    from {{ ref('fct_orders') }}
),

daily_totals as (
    select
        sum(revenue_orders) as revenue_orders,
        sum(gross_sales_amount) as gross_sales_amount,
        sum(refunded_amount) as refunded_amount,
        sum(net_revenue_amount) as net_revenue_amount
    from {{ ref('mart_daily_revenue') }}
)

select
    order_totals.*,
    daily_totals.net_revenue_amount as daily_net_revenue_amount
from order_totals
cross join daily_totals
where
    order_totals.revenue_orders != daily_totals.revenue_orders
    or order_totals.gross_sales_amount != daily_totals.gross_sales_amount
    or order_totals.refunded_amount != daily_totals.refunded_amount
    or order_totals.net_revenue_amount != daily_totals.net_revenue_amount
