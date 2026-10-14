{{ config(severity='warn') }}

-- Refunding more than was captured indicates a payment-system or extract problem.
select
    order_id,
    captured_amount,
    refunded_amount
from {{ ref('fct_orders') }}
where refunded_amount > captured_amount
