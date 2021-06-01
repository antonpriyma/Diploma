from parse_utils.lispInterpreter import parseTokens
from src.models.Program import Program
from src.plagiasm.checker import PlagiasmChecker


class ShinglesChecker(PlagiasmChecker):
    def check_programs(self, program1: str, program2: str):
        same = 0

        program1 = self.genshingle(program1)
        program2 = self.genshingle(program2)
        for shingle in program1:
            if shingle in program2:
                same = same + 1

        return same / float(len(program1) + len(program2) - same) * 100

    def genshingle(self, source):
        import binascii

        shingleLen = 5  # длина шингла
        out = []
        for i in range(len(source) - (shingleLen - 1)):
            out.append(
                binascii.crc32(
                    " ".join([x for x in source[i : i + shingleLen]]).encode("utf-8")
                )
            )

        return set(out)


if __name__ == "__main__":
    f1 = open("code1.txt", "r")
    code1 = f1.read()

    f2 = open("code2.txt", "r")
    code2 = f2.read()

    p1 = Program(type=1, source_code=code1, owner_email="kek", date=123)
    p2 = Program(type=1, source_code=code2, owner_email="kek", date=123)

    p1.set_tokens(parseTokens(code1))
    p2.set_tokens(parseTokens(code2))

    print(",".join(p2.tokens))

    checker = ShinglesChecker()

    print(checker.check_programs(p1.tokens, p2.tokens))
