{#
    Raw tables are append-only per batch. Staging keeps the most recently loaded
    valid version of each business key; quarantined rows are excluded.
#}
{% macro latest_valid_records(relation, business_key) %}
    select ranked.*
    from (
        select
            src.*,
            row_number() over (
                partition by trim(src.{{ business_key }})
                order by src._loaded_at desc, src._batch_id desc, src._source_line desc
            ) as _version_rank
        from {{ relation }} as src
        where not src._is_rejected
    ) as ranked
    where ranked._version_rank = 1
{% endmacro %}
