select
    product_id,
    sku,
    product_name,
    category,
    list_price,
    is_active,
    created_at
from {{ ref('stg_marketplace__products') }}
