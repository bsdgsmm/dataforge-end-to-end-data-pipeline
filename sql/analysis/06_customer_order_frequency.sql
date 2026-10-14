-- Distribution of customers by number of revenue-eligible orders, with the average
-- days between first and last order for each bucket.
with bucketed as (
    select
        least(revenue_orders, 5) as bucket_order,
        case
            when revenue_orders >= 5 then '5+'
            else revenue_orders::text
        end as revenue_orders_bucket,
        days_between_first_and_last_order,
        lifetime_net_revenue_amount
    from marts.mart_customer_order_summary
)

select
    revenue_orders_bucket,
    count(*) as customers,
    round(count(*)::numeric / sum(count(*)) over (), 4) as share_of_customers,
    round(avg(days_between_first_and_last_order), 1) as avg_days_first_to_last_order,
    sum(lifetime_net_revenue_amount) as net_revenue_amount
from bucketed
group by bucket_order, revenue_orders_bucket
order by bucket_order;
