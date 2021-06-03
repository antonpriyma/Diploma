from mysql import connector

from src.models.Program import Program
from src.models.Test import Test
from src.program.interfaces import RepositoryInterface


class Repository(RepositoryInterface):
    def __init__(self, conn: connector.connection):
        self.conn = conn

    def save_program(self, program):
        self.conn.cursor().execute(
            """
            INSERT INTO programs 
            (source_code, tokenized_code, email, name, type) 
            values (%s, %s, %s, %s, %s)""",
            (
                program.source_code,
                program.tokens,
                program.owner_email,
                program.owner_name,
                program.type,
            ),
        )

        self.conn.commit()

    def get_programs_by_type(self, type: int):
        with self.conn.cursor() as cursor:
            cursor.execute(f"SELECT * from programs where type = {type}")
            raw_programs = cursor

            programs = [
                Program(
                    type=raw_program[5],
                    source_code=raw_program[1],
                    owner_email=raw_program[3],
                    owner_name=raw_program[4],
                    tokens=raw_program[2],
                )
                for raw_program in raw_programs
            ]

            return programs

    def get_tests_by_type(self, type: int):
        with self.conn.cursor() as cursor:
            cursor.execute(f"SELECT * FROM tests where program_type = {type}")

            raw_tests = cursor.fetchall()
            tests = [
                Test(program_type=raw_test[0], input=raw_test[1], expected=raw_test[2])
                for raw_test in raw_tests
            ]

            return tests

    def get_programs_by_type_and_user(self, type, owner_email):
        with self.conn.cursor() as cursor:
            cursor.execute(
                f"SELECT * from programs where type = {type} and email = '{owner_email}'"
            )
            raw_programs = cursor.fetchall()

            programs = [
                Program(
                    type=raw_program[5],
                    source_code=raw_program[1],
                    owner_email=raw_program[3],
                    owner_name=raw_program[4],
                    tokens=raw_program[2],
                )
                for raw_program in raw_programs
            ]

            return programs
