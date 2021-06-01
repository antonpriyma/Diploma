drop table  if exists programs cascade;
create table programs(
    id bigserial not null  primary key,
    source_code varchar not null,
    tokenized_code varchar not null,
    email varchar not null,
    type int
);

drop table if exists tests cascade;
create table tests(
    prorgram_type int not null,
    input varchar not null,
    expected varchar not null
)