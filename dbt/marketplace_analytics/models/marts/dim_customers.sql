select
    customer_id,
    email,
    first_name,
    last_name,
    country_code,
    city,
    signed_up_at,
    (signed_up_at at time zone 'UTC')::date as signup_date
from {{ ref('stg_marketplace__customers') }}
