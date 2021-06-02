drop table  if exists programs cascade;
create table programs(
    id int auto_increment not null  primary key,
    source_code TEXT not null,
    tokenized_code TEXT not null,
    email TEXT not null,
    type int
);