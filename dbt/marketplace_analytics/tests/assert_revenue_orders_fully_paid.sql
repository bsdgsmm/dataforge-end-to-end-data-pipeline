{{ config(severity='warn') }}

-- Revenue-eligible orders should have captured exactly their net sales.
select
    order_id,
    net_sales_amount,
    captured_amount,
    payment_balance_amount
from {{ ref('fct_orders') }}
where
    is_revenue_eligible
    and abs(payment_balance_amount) > 0.01
