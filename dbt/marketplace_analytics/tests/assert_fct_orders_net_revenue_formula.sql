-- Net revenue must equal net sales minus refunds for revenue-eligible orders and be zero otherwise.
select
    order_id,
    is_revenue_eligible,
    net_sales_amount,
    refunded_amount,
    net_revenue_amount
from {{ ref('fct_orders') }}
where
    (is_revenue_eligible and net_revenue_amount != net_sales_amount - refunded_amount)
    or (not is_revenue_eligible and net_revenue_amount != 0)
