-- Repeat customer rate: customers with two or more revenue-eligible orders divided by
-- customers with at least one revenue-eligible order.
select
    count(*) filter (where revenue_orders >= 1) as purchasing_customers,
    count(*) filter (where is_repeat_customer) as repeat_customers,
    round(
        count(*) filter (where is_repeat_customer)::numeric
        / nullif(count(*) filter (where revenue_orders >= 1), 0),
        4
    ) as repeat_customer_rate
from marts.mart_customer_order_summary;
