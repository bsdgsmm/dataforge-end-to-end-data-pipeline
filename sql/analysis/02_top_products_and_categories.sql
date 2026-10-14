-- Best-performing products and categories by net revenue
-- (net sales minus refunds allocated to order lines by net-sales share).
with category_totals as (
    select
        category,
        sum(units_sold) as units_sold,
        sum(net_sales_amount) as net_sales_amount,
        sum(net_revenue_amount) as net_revenue_amount
    from marts.mart_product_performance
    group by category
)

select
    'category' as ranking_level,
    category as ranking_name,
    null as product_id,
    units_sold,
    net_sales_amount,
    net_revenue_amount,
    rank() over (order by net_revenue_amount desc) as net_revenue_rank
from category_totals

union all

select
    'product' as ranking_level,
    product_name as ranking_name,
    product_id,
    units_sold,
    net_sales_amount,
    net_revenue_amount,
    net_revenue_rank
from marts.mart_product_performance
where net_revenue_rank <= 10

order by ranking_level, net_revenue_rank;
