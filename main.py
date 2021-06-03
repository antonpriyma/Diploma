import subprocess
from venv import logger

from mysql.connector import connect, Error

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

    assert cfg.getPropertyWithDefault("res_path", "") != ""


if __name__ == "__main__":
    cfg = config.load("config.yaml")

    validate_cfg(cfg)

    reader = None
    try:
        reader = EmailReader(
            cfg.getProperty("email.login"),
            cfg.getProperty("email.password"),
            cfg.getProperty("email.server"),
            cfg.getProperty("email.subject_prefix"),
            cfg.getProperty("email.users"),
            "smtp.gmail.com",
        )
    except:
        print("Bad email credentials")
        exit(1)

    connection = None
    try:
        connection = connect(
            user=cfg.getProperty("db.user"),
            password=cfg.getProperty("db.password"),
            host=cfg.getProperty("db.host"),
            port=cfg.getProperty("db.port"),
        )
    except:
        print("Can`t connect to db")
        exit(1)

    cur = connection.cursor()
    connection.autocommit = True
    try:
        cur.execute(f'CREATE DATABASE {cfg.getProperty("db.dbname")}')
    except Error:
        connection = connect(
            user=cfg.getProperty("db.user"),
            password=cfg.getProperty("db.password"),
            host=cfg.getProperty("db.host"),
            port=cfg.getProperty("db.port"),
            database=cfg.getProperty("db.dbname"),
        )

    connection = connect(
        user=cfg.getProperty("db.user"),
        password=cfg.getProperty("db.password"),
        host=cfg.getProperty("db.host"),
        port=cfg.getProperty("db.port"),
        database=cfg.getProperty("db.dbname"),
    )

    connection.cursor().execute(
        """
create table if not exists programs(
    id int auto_increment not null  primary key,
    source_code TEXT not null,
    tokenized_code TEXT not null,
    email TEXT not null,
    name TEXT not null,
    type int
);"""
    )
    connection.commit()

    repo = Repository(connection)

    # test scheme path
    try:
        process = subprocess.Popen(
            [cfg.getProperty("tester.scheme_path"), "test.scm"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = process.communicate()
    except:
        print("Bad scheme path")
        exit(1)

    tester = Tester(
        cfg.getProperty("tester.scheme_path"), cfg.getProperty("tester.tests")
    )
    usecase = Usecase(
        repo,
        reader,
        tester,
        ShinglesChecker(),
        LevinstainChecker(),
        res_path=cfg.getProperty("res_path"),
    )

    programs = reader.read_programs()
    res = usecase.process_programs(programs)
