from gst.gst import token_comparison
from src.models.Program import Program


class PlagiasmAgregatedResult(object):
    def __init__(self, shingles_result: int = 0, levenstain_result: int = 0):
        self.shingles_result = shingles_result
        self.levenstain_result = levenstain_result

    def get_general_similarity(self):
        return (self.shingles_result + self.levenstain_result) / 2.0

    def __str__(self):
        return f"Совпадение шинглов: {self.shingles_result}, Расстояние Левенштайна: {self.levenstain_result}"


class PlagiasmResultWithInfo(PlagiasmAgregatedResult):
    def __init__(
        self,
        type: int = 0,
        sender_email: str = "",
        shingles_result: int = 0,
        levenstain_result: int = 0,
        success: bool = True,
        sender_program: Program = None,
        from_program: Program = None,
        from_email: str = "",
    ):
        super().__init__(shingles_result, levenstain_result)
        self.success = success
        self.type = type
        self.from_email = from_email
        self.sender_email = sender_email
        self.sender_program = sender_program
        self.from_program = from_program
        self.similar_sources = ""

    def calculate_similar_sources(self):
        tokens1 = [token[0] for token in self.from_program.token_list]
        tokens2 = [token[0] for token in self.sender_program.token_list]

        comp = token_comparison(tokens1, tokens2, 5)

        plagiasm_sources_1 = []
        for c in comp:
            program_1_start = self.from_program.token_list[c["tok_1_pos"]][1]
            program_1_end = self.from_program.token_list[
                c["tok_1_pos"] + c["length"] - 1
            ][1]

            plagiasm_source_1 = (program_1_start, program_1_end)

            plagiasm_sources_1.append(plagiasm_source_1)

        p1_sources = []

        for s in plagiasm_sources_1:
            p1_sources.append(self.from_program.source_code[s[0] - 1 : s[1] - 1])

        self.similar_sources = "\n\n------\n\n".join(p1_sources)
