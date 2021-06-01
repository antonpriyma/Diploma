import numpy as np
from pip._vendor.msgpack.fallback import xrange

from parse_utils.lispInterpreter import parseTokens
from src.models.Program import Program
from src.plagiasm.checker import PlagiasmChecker


class LevinstainChecker(PlagiasmChecker):
    def check_programs(self, program1: str, program2: str):
        size_x = len(program1) + 1
        size_y = len(program2) + 1
        matrix = np.zeros((size_x, size_y))
        for x in xrange(size_x):
            matrix[x, 0] = x
        for y in xrange(size_y):
            matrix[0, y] = y

        for x in xrange(1, size_x):
            for y in xrange(1, size_y):
                if program1[x - 1] == program2[y - 1]:
                    matrix[x, y] = min(
                        matrix[x - 1, y] + 1, matrix[x - 1, y - 1], matrix[x, y - 1] + 1
                    )
                else:
                    matrix[x, y] = min(
                        matrix[x - 1, y] + 1,
                        matrix[x - 1, y - 1] + 1,
                        matrix[x, y - 1] + 1,
                    )

        max_len = max(len(program1), len(program2))
        return 100 * (1 - matrix[size_x - 1, size_y - 1] / max_len)


if __name__ == "__main__":
    f1 = open("code1.txt", "r")
    code1 = f1.read()

    f2 = open("code2.txt", "r")
    code2 = f2.read()

    p1 = Program(type=1, source_code=code1, owner_email="kek", date=123)
    p2 = Program(type=1, source_code=code2, owner_email="kek", date=123)

    p1.set_tokens(parseTokens(code1))
    p2.set_tokens(parseTokens(code2))

    checker = LevinstainChecker()

    print(checker.check_programs(p1.tokens, p2.tokens))
