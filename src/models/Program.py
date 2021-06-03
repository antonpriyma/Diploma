from parse_utils.lispInterpreter import LispToken, LispTokenTypes

special_forms = [
    "access",
    "define-syntax",
    "macro",
    "and",
    "delay",
    "make-environment",
    "begin",
    "do",
    "named-lambda",
    "bkpt",
    "fluid-let",
    "or",
    "case",
    "if",
    "quasiquote",
    "cond",
    "in-package",
    "quote",
    "cons-stream",
    "lambda",
    "scode-quote",
    "declare",
    "let",
    "sequence",
    "default-object?",
    "let*",
    "set!",
    "define",
    "let-syntax",
    "the-environment",
    "define-integrable",
    "letrec",
    "unassigned?",
    "define-macro",
    "local-declare",
    "using-syntax",
    "define-structure",
]

standart_procedures = [
    "not",
    "boolean?",
    "eqv?",
    "eq?",
    "equal?",
    "pair?",
    "cons",
    "car",
    "cdr",
    "set-car",
    "set-cdr",
    "caar",
    "cadr",
    "cdddar",
    "cddddr",
    "null?",
    "list?",
    "list",
    "length",
    "append",
    "reverse",
    "list-tail",
    "list-ref",
    "memq",
    "memv",
    "member",
    "assq",
    "assv",
    "assoc",
    "symbol?",
    "symbol->string",
    "string->symbol",
    "number?",
    "complex?",
    "real?",
    "rational?",
    "integer?",
    "exact?",
    "inexact?",
    ">",
    ">",
    "zero?",
    "positive?",
    "negative?",
    "odd?",
    "even?",
    "max",
    "min",
    "-",
    "-",
    "-",
    "abs",
    "quotient",
    "remainder",
    "modulo",
    "gcd",
    "lcm",
    "numerator",
    "denominator",
    "floor",
    "ceiling",
    "truncate",
    "round",
    "rationalize",
    "exp",
    "log",
    "sin",
    "cos",
    "tan",
    "asin",
    "acos",
    "atan",
    "atan",
    "sqrt",
    "expt",
    "make-rectangular",
    "make-polar",
    "real-part",
    "imag-part",
    "magnitude",
    "angle",
    "exact->inexact",
    "inexact->exact",
    "number->string",
    "number->string",
    "string->number",
    "string->number",
    "char?",
    "char",
    "char",
    "char>?",
    "char",
    "char>",
    "char-ci",
    "char-ci",
    "char-ci>?",
    "char-ci",
    "char-ci>",
    "char-alphabetic?",
    "char-numeric?",
    "char-whitespace?",
    "char-upper-case?",
    "char-lower-case?",
    "char->integer",
    "integer->char",
    "char-upcase",
    "char-downcase",
    "string?",
    "make-string",
    "make-string",
    "string",
    "string-length",
    "string-ref",
    "string-set",
    "string",
    "string-ci",
    "string",
    "string>?",
    "string",
    "string>",
    "string-ci",
    "string-ci>?",
    "string-ci",
    "string-ci>",
    "substring",
    "string-append",
    "string->list",
    "list->string",
    "string-copy",
    "string-fill",
    "vector?",
    "make-vector",
    "make-vector",
    "vector",
    "vector-length",
    "vector-ref",
    "vector-set",
    "vector->list",
    "list->vector",
    "vector-fill",
    "procedure?",
    "apply",
    "apply",
    "map",
    "for-each",
    "force",
    "call-with-current-continuation",
    "call-with-input-file",
    "call-with-output-file",
    "input-port?",
    "output-port?",
    "current-input-port",
    "current-output-port",
    "with-input-from-file",
    "with-output-to-file",
    "open-input-file",
    "open-output-file",
    "close-input-port",
    "close-output-port",
    "read",
    "read",
    "read-char",
    "read-char",
    "peek-char",
    "peek-char",
    "eof-object?",
    "char-ready?",
    "char-ready?",
    "write",
    "write",
    "display",
    "display",
    "newline",
    "newline",
    "write-char",
    "write-char",
    "load",
    "transcript-on",
    "transcript-off",
]


class Program:
    def __init__(
        self,
        type: int,
        source_code: str,
        owner_email: str = "",
        owner_name: str = "",
        date: float = 0,
        tokens="",
    ):
        self.type = type
        self.source_code = source_code
        self.owner_email = owner_email
        self.owner_name = owner_name
        self.date = date
        self.tokens = tokens

    def set_tokens(self, tokens):
        res = ""
        for token in tokens:
            if token.text in special_forms:
                token.tokenType = int(LispTokenTypes.SpecialForm) + list(
                    special_forms
                ).index(token.text)
            if token.text in standart_procedures:
                token.tokenType = int(LispTokenTypes.StandartProcedure)
            # print(f"{token.tokenType.__str__()}, '{token.text}'\n")
            res = res + str(int(token.tokenType))

        token_list = []
        for token in tokens:
            if token.text in special_forms:
                token.tokenType = int(LispTokenTypes.SpecialForm) + list(
                    special_forms
                ).index(token.text)
            if token.text in standart_procedures:
                token.tokenType = int(LispTokenTypes.StandartProcedure)
            # print(f"{token.tokenType.__str__()}, '{token.text}'\n")
            if (
                token.tokenType != LispTokenTypes.Identifier
                or token.text in special_forms
                or token.text in standart_procedures
            ):
                token_list.append((str((token.text)), token.pos))
            else:
                token_list.append(("<IDENT>", token.pos))

        # print(token_list)
        self.tokens = res
        self.token_list = token_list

    def get_tokens_str(self) -> str:
        return self.tokens
