class TestResult(object):
    def __init__(
        self,
        success: bool,
        test: str,
        expected: str,
        actual: str,
        type: int,
        sender_name: str,
        source_code: str = "",
        sender_email: str = "",
    ):
        self.success = success
        self.test = test
        self.expected = expected
        self.actual = actual
        self.type = type
        self.sender_name = sender_name
        self.source_code = source_code
        self.sender_email = sender_email
