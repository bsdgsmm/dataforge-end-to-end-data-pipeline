with source as (
    {{ latest_valid_records(source('raw', 'payments'), 'payment_id') }}
)

select
    trim(payment_id) as payment_id,
    trim(order_id) as order_id,
    lower(trim(transaction_type)) as transaction_type,
    lower(trim(payment_method)) as payment_method,
    lower(trim(payment_status)) as payment_status,
    trim(amount)::numeric(12, 2) as amount,
    trim(created_at)::timestamptz as created_at,
    _batch_id as source_batch_id,
    _loaded_at as source_loaded_at
from source
