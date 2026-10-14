with orders as (
    select * from {{ ref('fct_orders') }}
),

calendar as (
    select generate_series(min(order_date), max(order_date), interval '1 day')::date as revenue_date
    from orders
),

daily as (
    select
        order_date,
        count(*) as orders_placed,
        count(*) filter (where is_revenue_eligible) as revenue_orders,
        count(*) filter (where is_cancelled) as cancelled_orders,
        count(distinct customer_id) as ordering_customers,
        sum(units_sold) filter (where is_revenue_eligible) as units_sold,
        sum(gross_sales_amount) filter (where is_revenue_eligible) as gross_sales_amount,
        sum(discount_amount) filter (where is_revenue_eligible) as discount_amount,
        sum(net_sales_amount) filter (where is_revenue_eligible) as net_sales_amount,
        sum(refunded_amount) filter (where is_revenue_eligible) as refunded_amount,
        sum(net_revenue_amount) filter (where is_revenue_eligible) as net_revenue_amount
    from orders
    group by order_date
)

select
    calendar.revenue_date,
    coalesce(daily.orders_placed, 0)::integer as orders_placed,
    coalesce(daily.revenue_orders, 0)::integer as revenue_orders,
    coalesce(daily.cancelled_orders, 0)::integer as cancelled_orders,
    coalesce(daily.ordering_customers, 0)::integer as ordering_customers,
    coalesce(daily.units_sold, 0)::integer as units_sold,
    coalesce(daily.gross_sales_amount, 0)::numeric(14, 2) as gross_sales_amount,
    coalesce(daily.discount_amount, 0)::numeric(14, 2) as discount_amount,
    coalesce(daily.net_sales_amount, 0)::numeric(14, 2) as net_sales_amount,
    coalesce(daily.refunded_amount, 0)::numeric(14, 2) as refunded_amount,
    coalesce(daily.net_revenue_amount, 0)::numeric(14, 2) as net_revenue_amount,
    round(daily.net_sales_amount / nullif(daily.revenue_orders, 0), 2) as average_order_value
from calendar
left join daily
    on calendar.revenue_date = daily.order_date
