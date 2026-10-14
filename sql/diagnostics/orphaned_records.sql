-- Child records in the modeled layers whose parent is missing.
-- All counts should be zero; foreign-key constraints on the marts enforce this.
select
    'stg orders -> customers' as relationship,
    count(*) as orphaned_rows
from staging.stg_marketplace__orders as orders
left join staging.stg_marketplace__customers as customers
    on orders.customer_id = customers.customer_id
where customers.customer_id is null

union all

select
    'stg order_items -> orders' as relationship,
    count(*) as orphaned_rows
from staging.stg_marketplace__order_items as items
left join staging.stg_marketplace__orders as orders
    on items.order_id = orders.order_id
where orders.order_id is null

union all

select
    'stg order_items -> products' as relationship,
    count(*) as orphaned_rows
from staging.stg_marketplace__order_items as items
left join staging.stg_marketplace__products as products
    on items.product_id = products.product_id
where products.product_id is null

union all

select
    'stg payments -> orders' as relationship,
    count(*) as orphaned_rows
from staging.stg_marketplace__payments as payments
left join staging.stg_marketplace__orders as orders
    on payments.order_id = orders.order_id
where orders.order_id is null;
