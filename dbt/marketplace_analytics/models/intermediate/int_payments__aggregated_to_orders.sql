with payments as (
    select * from {{ ref('stg_marketplace__payments') }}
)

select
    order_id,
    count(*) as payment_transaction_count,
    count(*) filter (
        where transaction_type = 'charge' and payment_status = 'failed'
    ) as failed_charge_count,
    coalesce(sum(amount) filter (
        where transaction_type = 'charge' and payment_status = 'succeeded'
    ), 0)::numeric(12, 2) as captured_amount,
    coalesce(sum(amount) filter (
        where transaction_type = 'refund' and payment_status = 'succeeded'
    ), 0)::numeric(12, 2) as refunded_amount,
    coalesce(sum(amount) filter (
        where payment_status = 'pending'
    ), 0)::numeric(12, 2) as pending_amount,
    min(created_at) filter (
        where transaction_type = 'charge' and payment_status = 'succeeded'
    ) as first_captured_at,
    max(created_at) filter (
        where transaction_type = 'refund' and payment_status = 'succeeded'
    ) as last_refunded_at
from payments
group by order_id
