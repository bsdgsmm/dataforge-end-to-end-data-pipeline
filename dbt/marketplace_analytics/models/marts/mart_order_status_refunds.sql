with orders as (
    select
        *,
        date_trunc('month', order_date)::date as order_month
    from {{ ref('fct_orders') }}
),

monthly as (
    select
        order_month,
        count(*) as total_orders,
        count(*) filter (where order_status = 'pending') as pending_orders,
        count(*) filter (where order_status = 'processing') as processing_orders,
        count(*) filter (where order_status = 'shipped') as shipped_orders,
        count(*) filter (where order_status = 'delivered') as delivered_orders,
        count(*) filter (where is_cancelled) as cancelled_orders,
        count(*) filter (
            where is_cancelled and captured_amount > 0
        ) as cancelled_after_capture_orders,
        count(*) filter (where is_revenue_eligible) as revenue_orders,
        count(*) filter (where is_revenue_eligible and refund_status != 'none') as refunded_orders,
        count(*) filter (
            where is_revenue_eligible and refund_status = 'full'
        ) as fully_refunded_orders,
        count(*) filter (
            where is_revenue_eligible and refund_status = 'partial'
        ) as partially_refunded_orders,
        coalesce(sum(net_sales_amount) filter (where is_revenue_eligible), 0) as net_sales_amount,
        coalesce(sum(refunded_amount) filter (where is_revenue_eligible), 0) as refunded_amount
    from orders
    group by order_month
)

select
    order_month,
    total_orders::integer as total_orders,
    pending_orders::integer as pending_orders,
    processing_orders::integer as processing_orders,
    shipped_orders::integer as shipped_orders,
    delivered_orders::integer as delivered_orders,
    cancelled_orders::integer as cancelled_orders,
    cancelled_after_capture_orders::integer as cancelled_after_capture_orders,
    revenue_orders::integer as revenue_orders,
    refunded_orders::integer as refunded_orders,
    fully_refunded_orders::integer as fully_refunded_orders,
    partially_refunded_orders::integer as partially_refunded_orders,
    round(cancelled_orders::numeric / nullif(total_orders, 0), 4) as cancellation_rate,
    round(refunded_orders::numeric / nullif(revenue_orders, 0), 4) as refund_order_rate,
    net_sales_amount::numeric(14, 2) as net_sales_amount,
    refunded_amount::numeric(14, 2) as refunded_amount,
    round(refunded_amount / nullif(net_sales_amount, 0), 4) as refund_amount_rate
from monthly
