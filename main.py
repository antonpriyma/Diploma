import psycopg3

from parse_utils.lispInterpreter import parseTokens
from reader.read_inbox import EmailReader
from src.models.Program import Program
from src.plagiasm.ShinglesChecker import ShinglesChecker
from src.plagiasm.LevinstainChecker import LevinstainChecker
from src.program.repository.psql.repository import Repository
from src.program.usecase.usecase import Usecase
from src.tester.tester import Tester

import config_with_yaml as config


def validate_cfg(cfg):
    assert cfg.getPropertyWithDefault("email.login", "") != ""
    assert cfg.getPropertyWithDefault("email.server", "") != ""
    assert cfg.getPropertyWithDefault("email.password", "") != ""
    assert cfg.getPropertyWithDefault("email.subject_prefix", "") != ""
    assert cfg.getPropertyWithDefault("email.users", None) is not None

    assert cfg.getPropertyWithDefault("db.user", "") != ""
    assert cfg.getPropertyWithDefault("db.password", "") != ""
    assert cfg.getPropertyWithDefault("db.host", "") != ""
    assert cfg.getPropertyWithDefault("db.port", "") != ""
    assert cfg.getPropertyWithDefault("db.dbname", "") != ""

    assert cfg.getPropertyWithDefault("tester.scheme_path", "") != ""
    assert cfg.getPropertyWithDefault("tester.tests", None) is not None


if __name__ == "__main__":
    cfg = config.load("config.yaml")

    validate_cfg(cfg)

    reader = EmailReader(
        cfg.getProperty("email.login"),
        cfg.getProperty("email.password"),
        cfg.getProperty("email.server"),
        cfg.getProperty("email.subject_prefix"),
        cfg.getProperty("email.users"),
    )

    connection = psycopg3.connect(
        user=cfg.getProperty("db.user"),
        password=cfg.getProperty("db.password"),
        host=cfg.getProperty("db.host"),
        port=cfg.getProperty("db.port"),
    )

    cur = connection.cursor()
    connection.autocommit = True
    # sql.SQL and sql.Identifier are needed to avoid SQL injection attacks.
    try:
        cur.execute(f'CREATE DATABASE {cfg.getProperty("db.dbname")}')
    except psycopg3.errors.DuplicateDatabase:
        connection = psycopg3.connect(
            user=cfg.getProperty("db.user"),
            password=cfg.getProperty("db.password"),
            host=cfg.getProperty("db.host"),
            port=cfg.getProperty("db.port"),
            dbname=cfg.getProperty("db.dbname")
        )

    cur.execute("""
create table if not exists programs(
    id bigserial not null  primary key,
    source_code varchar not null,
    tokenized_code varchar not null,
    email varchar not null,
    type int
);

create table if not exists tests(
    prorgram_type int not null,
    input varchar not null,
    expected varchar not null
)""")

    repo = Repository(connection.cursor(), connection)
    tester = Tester(
        cfg.getProperty("tester.scheme_path"), cfg.getProperty("tester.tests")
    )
    usecase = Usecase(repo, tester, ShinglesChecker(), LevinstainChecker())

    programs = reader.read_programs()
    res = usecase.process_programs(programs)

    # for program in programs:
    #     tokenize_program(program)
    #
    # for program in programs:
    #     print(f'type: {program.type}, code: {program.source_code}, tokens: {program.tokens}')

    # plagiasmResult = checkProgramForPlagiasm(programs)
