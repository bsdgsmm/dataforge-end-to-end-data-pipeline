-- Orders whose payments do not reconcile or whose values look implausible.
select
    order_id,
    order_status,
    net_sales_amount,
    captured_amount,
    refunded_amount,
    payment_balance_amount,
    case
        when is_revenue_eligible and abs(payment_balance_amount) > 0.01
            then 'captured amount differs from net sales'
        when refunded_amount > captured_amount
            then 'refunded more than captured'
        when is_cancelled and captured_amount - refunded_amount > 0.01
            then 'cancelled order still holds captured funds'
        when net_sales_amount > 5000
            then 'unusually large order'
    end as issue
from marts.fct_orders
where
    (is_revenue_eligible and abs(payment_balance_amount) > 0.01)
    or refunded_amount > captured_amount
    or (is_cancelled and captured_amount - refunded_amount > 0.01)
    or net_sales_amount > 5000
order by order_id;
