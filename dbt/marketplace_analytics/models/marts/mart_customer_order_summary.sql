with customers as (
    select * from {{ ref('dim_customers') }}
),

order_summary as (
    select
        customer_id,
        count(*) as total_orders,
        count(*) filter (where is_revenue_eligible) as revenue_orders,
        count(*) filter (where is_cancelled) as cancelled_orders,
        min(ordered_at) as first_ordered_at,
        max(ordered_at) as last_ordered_at,
        sum(net_sales_amount) filter (where is_revenue_eligible) as net_sales_amount,
        sum(refunded_amount) filter (where is_revenue_eligible) as refunded_amount,
        sum(net_revenue_amount) filter (where is_revenue_eligible) as net_revenue_amount
    from {{ ref('fct_orders') }}
    group by customer_id
)

select
    customers.customer_id,
    customers.country_code,
    customers.signup_date,
    coalesce(order_summary.total_orders, 0)::integer as total_orders,
    coalesce(order_summary.revenue_orders, 0)::integer as revenue_orders,
    coalesce(order_summary.cancelled_orders, 0)::integer as cancelled_orders,
    order_summary.first_ordered_at,
    order_summary.last_ordered_at,
    (
        order_summary.last_ordered_at::date - order_summary.first_ordered_at::date
    ) as days_between_first_and_last_order,
    coalesce(order_summary.net_sales_amount, 0)::numeric(14, 2) as lifetime_net_sales_amount,
    coalesce(order_summary.refunded_amount, 0)::numeric(14, 2) as lifetime_refunded_amount,
    coalesce(order_summary.net_revenue_amount, 0)::numeric(14, 2) as lifetime_net_revenue_amount,
    round(
        order_summary.net_sales_amount / nullif(order_summary.revenue_orders, 0), 2
    ) as average_order_value,
    coalesce(order_summary.revenue_orders, 0) >= 2 as is_repeat_customer,
    case
        when coalesce(order_summary.total_orders, 0) = 0 then 'no_orders'
        when order_summary.revenue_orders = 0 then 'no_completed_orders'
        when order_summary.revenue_orders = 1 then 'one_time'
        else 'repeat'
    end as customer_segment
from customers
left join order_summary
    on customers.customer_id = order_summary.customer_id
