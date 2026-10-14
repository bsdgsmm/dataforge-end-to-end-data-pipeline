-- Line-level sales must add up exactly to the order-level sales measures.
with line_totals as (
    select
        order_id,
        sum(gross_sales_amount) as gross_sales_amount,
        sum(discount_amount) as discount_amount,
        sum(net_sales_amount) as net_sales_amount
    from {{ ref('fct_order_items') }}
    group by order_id
)

select
    orders.order_id,
    orders.gross_sales_amount,
    line_totals.gross_sales_amount as line_gross_sales_amount
from {{ ref('fct_orders') }} as orders
left join line_totals
    on orders.order_id = line_totals.order_id
where
    line_totals.order_id is null
    or orders.gross_sales_amount != line_totals.gross_sales_amount
    or orders.discount_amount != line_totals.discount_amount
    or orders.net_sales_amount != line_totals.net_sales_amount
