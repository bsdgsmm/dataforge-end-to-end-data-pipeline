with source as (
    {{ latest_valid_records(source('raw', 'customers'), 'customer_id') }}
)

select
    trim(customer_id) as customer_id,
    lower(trim(email)) as email,
    trim(first_name) as first_name,
    trim(last_name) as last_name,
    upper(trim(country_code)) as country_code,
    nullif(trim(city), '') as city,
    trim(signed_up_at)::timestamptz as signed_up_at,
    _batch_id as source_batch_id,
    _loaded_at as source_loaded_at
from source
