with orders as (
    select * from {{ ref('stg_marketplace__orders') }}
),

order_statuses as (
    select * from {{ ref('order_statuses') }}
),

item_totals as (
    select
        order_id,
        count(*) as item_count,
        sum(quantity) as units_sold,
        sum(gross_sales_amount) as gross_sales_amount,
        sum(discount_amount) as discount_amount,
        sum(net_sales_amount) as net_sales_amount
    from {{ ref('int_order_items__priced') }}
    group by order_id
),

payment_totals as (
    select * from {{ ref('int_payments__aggregated_to_orders') }}
)

select
    orders.order_id,
    orders.customer_id,
    orders.order_status,
    orders.ordered_at,
    (orders.ordered_at at time zone 'UTC')::date as order_date,
    orders.updated_at,
    orders.currency,
    order_statuses.is_revenue_eligible,
    orders.order_status = 'cancelled' as is_cancelled,
    coalesce(item_totals.item_count, 0) as item_count,
    coalesce(item_totals.units_sold, 0) as units_sold,
    coalesce(item_totals.gross_sales_amount, 0)::numeric(12, 2) as gross_sales_amount,
    coalesce(item_totals.discount_amount, 0)::numeric(12, 2) as discount_amount,
    coalesce(item_totals.net_sales_amount, 0)::numeric(12, 2) as net_sales_amount,
    coalesce(payment_totals.payment_transaction_count, 0) as payment_transaction_count,
    coalesce(payment_totals.failed_charge_count, 0) as failed_charge_count,
    coalesce(payment_totals.captured_amount, 0)::numeric(12, 2) as captured_amount,
    coalesce(payment_totals.refunded_amount, 0)::numeric(12, 2) as refunded_amount,
    payment_totals.first_captured_at,
    payment_totals.last_refunded_at
from orders
inner join order_statuses
    on orders.order_status = order_statuses.order_status
left join item_totals
    on orders.order_id = item_totals.order_id
left join payment_totals
    on orders.order_id = payment_totals.order_id
