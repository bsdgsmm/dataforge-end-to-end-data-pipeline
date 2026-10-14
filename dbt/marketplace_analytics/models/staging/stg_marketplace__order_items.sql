with source as (
    {{ latest_valid_records(source('raw', 'order_items'), 'order_item_id') }}
)

select
    trim(order_item_id) as order_item_id,
    trim(order_id) as order_id,
    trim(line_number)::integer as line_number,
    trim(product_id) as product_id,
    trim(quantity)::integer as quantity,
    trim(unit_price)::numeric(12, 2) as unit_price,
    trim(discount_amount)::numeric(12, 2) as discount_amount,
    _batch_id as source_batch_id,
    _loaded_at as source_loaded_at
from source
