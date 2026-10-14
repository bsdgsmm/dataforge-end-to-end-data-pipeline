select
    order_item_id,
    order_id,
    line_number,
    product_id,
    quantity,
    unit_price,
    (quantity * unit_price)::numeric(12, 2) as gross_sales_amount,
    discount_amount,
    (quantity * unit_price - discount_amount)::numeric(12, 2) as net_sales_amount
from {{ ref('stg_marketplace__order_items') }}
