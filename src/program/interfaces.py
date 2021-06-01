class UsecaseInterface(object):
    def check_programs_for_plagiasm(self, programs):
        return Exception("not implemented")

    def process_programs(self, programs):
        return Exception("not implemented")


class RepositoryInterface(object):
    def get_programs_by_type(self, type: int):
        return Exception("not implemented")

    def get_tests_by_type(self, type: int):
        return Exception("not implemented")

    def save_program(self, program):
        pass

    def get_programs_by_type_and_user(self, type, owner_email):
        pass
