import os
import subprocess
import tempfile
from typing import List

from src.models import Program
from src.models.Test import Test

from src.models.test_result import TestResult


class Tester(object):
    def __init__(self, scheme_path: str, tests):
        self.scheme_path = scheme_path

        self.tests = []
        if tests is not None:
            for test in tests:
                new_test = Test(test["type"], test["input"], test["expected"])
                self.tests.append(new_test)

    def test_program(self, program: Program) -> TestResult:
        for test in self.get_tests_by_type(program.type):
            result = self.run_scheme_test(program.source_code, test.input)

            if str(result) != str(test.expected):
                return TestResult(
                    False,
                    test.input,
                    test.expected,
                    result,
                    program.type,
                    program.owner_email,
                )

        return TestResult(True, "", "", "", program.type, program.owner_email)

    def run_scheme_test(self, source_code, input) -> str:

        if "#lang racket" in source_code:
            runnable_source_code = f"{source_code}\n{input}"
        else:
            runnable_source_code = f"#lang racket\n{source_code}\n{input}"

        f = tempfile.NamedTemporaryFile()
        f.write(str.encode(runnable_source_code))
        f.seek(os.SEEK_SET)

        # todo: make config path
        process = subprocess.Popen(
            [self.scheme_path, f.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()

        if len(stderr) > 0:
            return str(stderr)

        return stdout.decode("utf-8").replace("\n", "")

    def get_tests_by_type(self, type: str):
        res = []
        for test in self.tests:
            if str(test.program_type) == type:
                res.append(test)

        return res
