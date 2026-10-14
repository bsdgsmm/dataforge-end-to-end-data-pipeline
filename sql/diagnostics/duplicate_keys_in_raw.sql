-- Business keys that appear more than once within the same raw batch.
-- Exact copies are quarantined as duplicate_record; conflicting copies as
-- conflicting_duplicate_key. Both remain here for inspection.
select
    'customers' as entity,
    _batch_id,
    customer_id as business_key,
    count(*) as copies
from raw.customers
group by _batch_id, customer_id
having count(*) > 1

union all

select
    'products' as entity,
    _batch_id,
    product_id as business_key,
    count(*) as copies
from raw.products
group by _batch_id, product_id
having count(*) > 1

union all

select
    'orders' as entity,
    _batch_id,
    order_id as business_key,
    count(*) as copies
from raw.orders
group by _batch_id, order_id
having count(*) > 1

union all

select
    'order_items' as entity,
    _batch_id,
    order_item_id as business_key,
    count(*) as copies
from raw.order_items
group by _batch_id, order_item_id
having count(*) > 1

union all

select
    'payments' as entity,
    _batch_id,
    payment_id as business_key,
    count(*) as copies
from raw.payments
group by _batch_id, payment_id
having count(*) > 1

order by entity, _batch_id, business_key;
