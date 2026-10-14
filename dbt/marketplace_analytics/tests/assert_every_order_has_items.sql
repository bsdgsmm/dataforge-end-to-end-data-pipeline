-- Source validation quarantines orders without valid items, so none may reach the marts.
select
    order_id,
    item_count
from {{ ref('fct_orders') }}
where item_count = 0
