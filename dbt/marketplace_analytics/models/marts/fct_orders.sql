with orders as (
    select * from {{ ref('int_orders__enriched') }}
)

select
    order_id,
    customer_id,
    order_status,
    ordered_at,
    order_date,
    updated_at,
    currency,
    is_revenue_eligible,
    is_cancelled,
    item_count::integer as item_count,
    units_sold::integer as units_sold,
    gross_sales_amount,
    discount_amount,
    net_sales_amount,
    captured_amount,
    refunded_amount,
    (
        case
            when is_revenue_eligible then net_sales_amount - refunded_amount
            else 0
        end
    )::numeric(12, 2) as net_revenue_amount,
    (captured_amount - net_sales_amount)::numeric(12, 2) as payment_balance_amount,
    case
        when refunded_amount = 0 then 'none'
        when refunded_amount >= captured_amount then 'full'
        else 'partial'
    end as refund_status,
    failed_charge_count::integer as failed_charge_count,
    (
        case
            when is_revenue_eligible
                then row_number() over (
                        partition by customer_id, is_revenue_eligible
                        order by ordered_at, order_id
                    )
        end
    )::integer as customer_order_number,
    first_captured_at,
    last_refunded_at
from orders
