-- Cancellation rate = cancelled orders / all orders placed.
-- Refund order rate = revenue-eligible orders with any refund / revenue-eligible orders.
-- Refund amount rate = refunds / net sales of revenue-eligible orders.
select
    order_month,
    total_orders,
    cancelled_orders,
    cancellation_rate,
    revenue_orders,
    refunded_orders,
    fully_refunded_orders,
    partially_refunded_orders,
    refund_order_rate,
    refunded_amount,
    refund_amount_rate
from marts.mart_order_status_refunds

union all

select
    null as order_month,
    sum(total_orders) as total_orders,
    sum(cancelled_orders) as cancelled_orders,
    round(sum(cancelled_orders)::numeric / nullif(sum(total_orders), 0), 4) as cancellation_rate,
    sum(revenue_orders) as revenue_orders,
    sum(refunded_orders) as refunded_orders,
    sum(fully_refunded_orders) as fully_refunded_orders,
    sum(partially_refunded_orders) as partially_refunded_orders,
    round(
        sum(refunded_orders)::numeric / nullif(sum(revenue_orders), 0), 4
    ) as refund_order_rate,
    sum(refunded_amount) as refunded_amount,
    round(sum(refunded_amount) / nullif(sum(net_sales_amount), 0), 4) as refund_amount_rate
from marts.mart_order_status_refunds

order by order_month nulls last;
