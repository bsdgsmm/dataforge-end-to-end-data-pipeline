with items as (
    select * from {{ ref('int_order_items__priced') }}
),

orders as (
    select * from {{ ref('fct_orders') }}
),

allocated as (
    select
        items.order_item_id,
        items.order_id,
        orders.customer_id,
        items.product_id,
        items.line_number,
        orders.ordered_at,
        orders.order_date,
        orders.order_status,
        orders.is_revenue_eligible,
        items.quantity,
        items.unit_price,
        items.gross_sales_amount,
        items.discount_amount,
        items.net_sales_amount,
        (
            case
                when orders.net_sales_amount > 0
                    then round(
                            orders.refunded_amount
                            * items.net_sales_amount
                            / orders.net_sales_amount,
                            2
                        )
                else 0
            end
        )::numeric(12, 2) as allocated_refund_amount
    from items
    inner join orders
        on items.order_id = orders.order_id
)

select
    *,
    (
        case
            when is_revenue_eligible then net_sales_amount - allocated_refund_amount
            else 0
        end
    )::numeric(12, 2) as net_revenue_amount
from allocated
