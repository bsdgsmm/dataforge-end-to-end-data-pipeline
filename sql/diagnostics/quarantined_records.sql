-- Quarantined source rows with their rejection reasons and source line numbers,
-- for tracing an issue back to the delivered file.
select
    'customers' as entity,
    _batch_id,
    _source_file,
    _source_line,
    customer_id as business_key,
    _rejection_reasons
from raw.customers
where _is_rejected

union all

select
    'products' as entity,
    _batch_id,
    _source_file,
    _source_line,
    product_id as business_key,
    _rejection_reasons
from raw.products
where _is_rejected

union all

select
    'orders' as entity,
    _batch_id,
    _source_file,
    _source_line,
    order_id as business_key,
    _rejection_reasons
from raw.orders
where _is_rejected

union all

select
    'order_items' as entity,
    _batch_id,
    _source_file,
    _source_line,
    order_item_id as business_key,
    _rejection_reasons
from raw.order_items
where _is_rejected

union all

select
    'payments' as entity,
    _batch_id,
    _source_file,
    _source_line,
    payment_id as business_key,
    _rejection_reasons
from raw.payments
where _is_rejected

order by _batch_id, entity, _source_line;
