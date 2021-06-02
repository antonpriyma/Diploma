import logging
import os
from datetime import datetime

from parse_utils.lispInterpreter import parseTokens
from reader.read_inbox import EmailReader
from src.models import Program
from src.models.Test import Test
from src.models.plagiasm_aggregated_result import (
    PlagiasmAgregatedResult,
    PlagiasmResultWithInfo,
)
from src.models.work_result import WorkResult
from src.plagiasm.checker import PlagiasmChecker
from src.program.interfaces import UsecaseInterface, RepositoryInterface
from src.tester.tester import Tester


class Usecase(UsecaseInterface):
    def __init__(
            self,
            programs: RepositoryInterface,
            email: EmailReader,
            tester: Tester,
            shingles: PlagiasmChecker,
            levinstain: PlagiasmChecker,
            shingles_treshold: int = 90,
            levinstain_treshold: int = 90,
    ):
        self.programs = programs
        self.tester = tester
        self.shingles = shingles
        self.levinastain = levinstain
        self.shingles_treshold = shingles_treshold
        self.levinstain_treshold = levinstain_treshold
        self.email = email

    def save_res_to_system(self, res: WorkResult):
        time = datetime.now()
        path = f"results/{time}"

        try:
            os.makedirs(path)
        except OSError:
            print("Creation of the directory %s failed" % path)

        for result in res.success_results:
            path_success = f"results/{time}/{result['email']}/success/{result['type']}"
            os.makedirs(path_success)
            f = open(f"{path_success}/code.scm", "w")
            f.write(result["source_code"])
            f.close()

            self.email.send_success_email(result['email'], result['type'])

        for test in res.failed_tests:
            path_tests = f"results/{time}/{test.email}/failed_tests/{test.type}"
            os.makedirs(path_tests)
            f = open(f"{path_tests}/code.scm", "w")
            f.write(test.source_code)
            f.close()

            self.email.send_failed_test(test)

        for plagiasm in res.failed_plagiasm:
            path_plagiasm = f"results/{time}/{plagiasm.sender_email}/failed_plagiasm/{plagiasm.type}"
            os.makedirs(path_plagiasm)
            f = open(f"{path_plagiasm}/code.scm", "w")
            f.write(plagiasm.from_program.source_code)
            f.close()

            f = open(f"{path_plagiasm}/code_similar.scm", "w")
            f.write(plagiasm.from_program.source_code)
            f.close()

            f = open(f"{path_plagiasm}/similar_sources.txt", "w")
            f.write(plagiasm.similar_sources)
            f.close()

        f = open(f"{path}/report.txt", "w")
        f.write(str(res))
        f.close()

    def process_programs(self, programs):
        tests_res = []
        plagiasms_res = []
        for program in programs:
            # check if programs was accepted before
            old_programs = self.programs.get_programs_by_type_and_user(
                program.type, program.owner_email
            )
            if len(old_programs) > 0:
                # Program already accepted
                continue

            # testing program
            test_res = self.tester.test_program(program)
            tests_res.append(test_res)

            if not test_res.success:
                # TODO: log failed test and send email
                # logging.warning(
                #     f"Test fail: expected: {test_res.expected}, actual: {test_res.actual}, input: {test_res.test}"
                # )
                continue

            # check program for plagiasm
            plagiasm, plagiasm_res = self.check_program_for_plagiasm(program)
            plagiasms_res.append(plagiasm_res)
            if plagiasm:
                # logging.warning(f"Plagiasm fail: {plagiasm_res}")
                continue

            # all checks success
            # todo: log program accepted and send email
            # logging.warning("Program accepted")
            self.programs.save_program(program)

        res = WorkResult(tests=tests_res, plagiasm=plagiasms_res)

        self.save_res_to_system(res)

    def check_programs_for_plagiasm(self, programs):
        #     Tokenize code
        for program in programs:
            self.check_program_for_plagiasm(program)

    def check_program_for_plagiasm(self, program: Program):
        self.tokenize_program(program)

        old_programs = self.programs.get_programs_by_type(program.type)

        max_plagiasm_res = PlagiasmResultWithInfo()

        for old_program in old_programs:
            plagiasm_res = self.compare_with_program(program, old_program)

            if (
                    plagiasm_res.get_general_similarity()
                    > max_plagiasm_res.get_general_similarity()
            ):
                max_plagiasm_res = plagiasm_res

        if (
                max_plagiasm_res.shingles_result > self.shingles_treshold
                or max_plagiasm_res.levenstain_result > self.levinstain_treshold
        ):
            max_plagiasm_res.success = False

            self.tokenize_program(max_plagiasm_res.from_program)

            max_plagiasm_res.calculate_similar_sources()
            return True, max_plagiasm_res

        return (
            False,
            PlagiasmResultWithInfo(
                success=True, type=program.type, sender_email=program.owner_email
            ),
        )

    def tokenize_program(self, program):
        tokens = parseTokens(str(program.source_code).replace("#lang racket", ""))
        if not tokens:
            #     todo: err
            print("err while parsing")

        program.set_tokens(tokens)

    def compare_with_program(self, program: Program, old_program: Program):
        shingles_result = self.shingles.check_programs(
            program.get_tokens_str(), old_program.get_tokens_str()
        )
        levenstain_result = self.levinastain.check_programs(
            program.get_tokens_str(), old_program.get_tokens_str()
        )

        return PlagiasmResultWithInfo(
            type=program.type,
            from_email=old_program.owner_email,
            sender_email=program.owner_email,
            shingles_result=shingles_result,
            levenstain_result=levenstain_result,
            sender_program=program,
            from_program=old_program,
        )
