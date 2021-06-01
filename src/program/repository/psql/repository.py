import psycopg3

from src.models.Program import Program
from src.models.Test import Test
from src.program.interfaces import RepositoryInterface
from psycopg3 import connection


class Repository(RepositoryInterface):
    def __init__(self, db: psycopg3.Cursor, conn: psycopg3.Connection):
        self.db = db
        self.conn = conn

    def save_program(self, program):
        self.db.execute(
            f"INSERT INTO programs (source_code, tokenized_code, email, type) values ('{program.source_code}', '{program.tokens}', '{program.owner_email}', '{program.type}')"
        )

        self.conn.commit()

    def get_programs_by_type(self, type: int):
        self.db.execute(f"SELECT * from programs where type = {type}")
        raw_programs = self.db.fetchall()

        programs = [
            Program(
                type=raw_program[4],
                source_code=raw_program[1],
                owner_email=raw_program[3],
                tokens=raw_program[2],
            )
            for raw_program in raw_programs
        ]

        return programs

    def get_tests_by_type(self, type: int):
        self.db.execute(f"SELECT * FROM tests where program_type = {type}")

        raw_tests = self.db.fetchall()
        tests = [
            Test(program_type=raw_test[0], input=raw_test[1], expected=raw_test[2])
            for raw_test in raw_tests
        ]

        return tests

    def get_programs_by_type_and_user(self, type, owner_email):
        self.db.execute(
            f"SELECT * from programs where type = {type} and email = '{owner_email}'"
        )
        raw_programs = self.db.fetchall()

        programs = [
            Program(
                type=raw_program[4],
                source_code=raw_program[1],
                owner_email=raw_program[3],
                tokens=raw_program[2],
            )
            for raw_program in raw_programs
        ]

        return programs
