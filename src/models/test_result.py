class TestResult(object):
    def __init__(
        self,
        success: bool,
        test: str,
        expected: str,
        actual: str,
        type: int,
        email: str,
        source_code: str = "",
    ):
        self.success = success
        self.test = test
        self.expected = expected
        self.actual = actual
        self.type = type
        self.email = email
        self.source_code = source_code
