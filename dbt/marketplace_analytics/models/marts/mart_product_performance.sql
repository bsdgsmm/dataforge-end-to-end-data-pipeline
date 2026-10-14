with products as (
    select * from {{ ref('dim_products') }}
),

sales as (
    select
        product_id,
        count(distinct order_id) as orders_count,
        sum(quantity) as units_sold,
        sum(gross_sales_amount) as gross_sales_amount,
        sum(discount_amount) as discount_amount,
        sum(net_sales_amount) as net_sales_amount,
        sum(allocated_refund_amount) as allocated_refund_amount,
        sum(net_revenue_amount) as net_revenue_amount,
        min(order_date) as first_sold_date,
        max(order_date) as last_sold_date
    from {{ ref('fct_order_items') }}
    where is_revenue_eligible
    group by product_id
),

combined as (
    select
        products.product_id,
        products.sku,
        products.product_name,
        products.category,
        products.list_price,
        products.is_active,
        coalesce(sales.orders_count, 0)::integer as orders_count,
        coalesce(sales.units_sold, 0)::integer as units_sold,
        coalesce(sales.gross_sales_amount, 0)::numeric(14, 2) as gross_sales_amount,
        coalesce(sales.discount_amount, 0)::numeric(14, 2) as discount_amount,
        coalesce(sales.net_sales_amount, 0)::numeric(14, 2) as net_sales_amount,
        coalesce(sales.allocated_refund_amount, 0)::numeric(14, 2) as allocated_refund_amount,
        coalesce(sales.net_revenue_amount, 0)::numeric(14, 2) as net_revenue_amount,
        sales.first_sold_date,
        sales.last_sold_date
    from products
    left join sales
        on products.product_id = sales.product_id
)

select
    *,
    rank() over (order by net_revenue_amount desc) as net_revenue_rank,
    rank() over (
        partition by category order by net_revenue_amount desc
    ) as category_net_revenue_rank,
    round(
        net_revenue_amount / nullif(sum(net_revenue_amount) over (partition by category), 0),
        4
    ) as share_of_category_net_revenue
from combined
