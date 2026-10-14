with source as (
    {{ latest_valid_records(source('raw', 'products'), 'product_id') }}
)

select
    trim(product_id) as product_id,
    upper(trim(sku)) as sku,
    trim(product_name) as product_name,
    trim(category) as category,
    trim(list_price)::numeric(12, 2) as list_price,
    trim(is_active)::boolean as is_active,
    trim(created_at)::timestamptz as created_at,
    _batch_id as source_batch_id,
    _loaded_at as source_loaded_at
from source
