with source as (
    {{ latest_valid_records(source('raw', 'orders'), 'order_id') }}
)

select
    trim(order_id) as order_id,
    trim(customer_id) as customer_id,
    lower(trim(order_status)) as order_status,
    trim(ordered_at)::timestamptz as ordered_at,
    trim(updated_at)::timestamptz as updated_at,
    upper(trim(currency)) as currency,
    _batch_id as source_batch_id,
    _loaded_at as source_loaded_at
from source
