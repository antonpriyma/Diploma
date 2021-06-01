from src.models.plagiasm_aggregated_result import PlagiasmResultWithInfo
from src.models.test_result import TestResult


class WorkResult(object):
    def __init__(self, tests, plagiasm):
        self.tests = tests
        self.plagiasm = plagiasm

        self.success_tests = []
        for test in self.tests:
            if test.success:
                self.success_tests.append(test)

        self.failed_tests = []
        for test in self.tests:
            if not test.success:
                self.failed_tests.append(test)

        self.success_plagiasm = []
        for plagiasm in self.plagiasm:
            if plagiasm.success:
                self.success_plagiasm.append(plagiasm)

        self.failed_plagiasm = []
        for plagiasm in self.plagiasm:
            if not plagiasm.success:
                self.failed_plagiasm.append(plagiasm)

        self.success_results = []
        for plagiasm in self.success_plagiasm:
            for test in self.success_tests:
                if plagiasm.type == test.type and plagiasm.sender_email == test.email:
                    self.success_results.append(
                        {
                            "email": plagiasm.sender_email,
                            "type": plagiasm.type,
                            "source_code": test.source_code,
                        }
                    )

    def __str__(self) -> str:
        res = """
Тесты:
    Прошли:
        {success_tests}
    
    Не прошли:    
        {failed_tests}      
        
Плагиат:
    Успешно:          
        {success_plagiasm}

    Замечен:        
        {failed_plagiasm}

Принято:
    {success_results}        
        """

        success = ""
        for test in self.tests:
            if test.success:
                success += f"{test.email}, задача №{test.type}"
                success += "\n\t\t"

        failed = ""
        for test in self.tests:
            if not test.success:
                failed += f"{test.email}, задача №{test.type}, тест: [команда: {test.test}, ожидалось: {test.expected}, получено: {test.actual}]"
                failed += "\n\t\t"

        success_plagiasm = ""
        for plagiasm in self.plagiasm:
            if plagiasm.success:
                success_plagiasm += f"{plagiasm.sender_email}, задача №{plagiasm.type}"
                success_plagiasm += "\n\t\t"

        failed_plagiasm = ""
        for plagiasm in self.plagiasm:
            if not plagiasm.success:
                failed_plagiasm += (
                    f"{plagiasm.sender_email}, задача №{plagiasm.type}, cписано у {plagiasm.from_email}. "
                    f"Результат: [{plagiasm}] "
                )
                failed_plagiasm += "\n\t\t"

        success_results = ""
        for result in self.success_results:
            success_results += f"{result['email']}, задача №{result['type']} "
            success_results += "\n\t\t"

        return res.format(
            success_tests=success,
            failed_tests=failed,
            success_plagiasm=success_plagiasm,
            failed_plagiasm=failed_plagiasm,
            success_results=success_results,
        )
