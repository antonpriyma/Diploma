import sys
from enum import Enum, IntEnum
import unittest
import functools
import numpy as np

LispLexerDebug = False


###############################################################################
## AST definitions

class LispAST:
    def __init__(self):
        pass

    def eval(self, env):
        raise Exception("'eval' not implemented for type: " + type(self).__name__)


class LispAST_void(LispAST):
    def __init__(self, _=False, __=False, ___=False, ____=False):
        pass


class LispAST_Real:
    def __init__(self, sign, numerator, denominator, text):
        self.sign = sign
        self.numerator = numerator
        self.denominator = denominator
        self.text = text

    def __repr__(self):
        return "LispAST_Real(%s,%s,%s,\"%s\")" % (self.sign, self.numerator, self.denominator, self.text)

    def __str__(self):
        return str(self.text)

    def getFloat(self):
        return self.sign * self.numerator / self.denominator

    def getInt(self):
        return self.sign * self.numerator

    def equals(self, other):
        return (np.isclose(self.sign, other.sign)
                and np.isclose(self.numerator, other.numerator)
                and np.isclose(self.denominator, other.denominator))


class LispAST_Number(LispAST):
    def __init__(self, radix=10, exactness=True, real=0, imag=0, text=""):
        self.radix = radix
        self.exactness = exactness
        self.real = real
        self.imag = imag
        self.text = text

    def __repr__(self):
        return "LispAST_Number(%s,%s,%s,%s,\"%s\")" % (self.radix, self.exactness, self.real, self.imag, self.text)

    def __str__(self):
        return str(self.text)

    def eval(self, env):
        return LispEvalContext(env, LispValue(self, LispValueTypes.Number))

    def getComplex(self):
        return self.real.getFloat() + (self.imag.getFloat() * 1j)

    def equals(self, other):
        return (self.radix == other.radix
                and self.exactness == other.exactness
                and self.real.equals(other.real)
                and self.imag.equals(other.imag))


class LispAST_token(LispAST):
    def __init__(self, tokenType, text, extra=[]):
        self.tokenType = tokenType
        self.text = text
        self.extra = extra

    def __repr__(self):
        return "LispAST_token(%s, \"%s\", %s)" % (self.tokenType, self.text, self.extra)

    def __str__(self):
        return self.text

    def eval(self, env):
        valueType = tokenTypeToValue(self.tokenType)
        return LispEvalContext(env, LispValue(self.extra, valueType))


class LispAST_Variable:
    def __init__(self, id):
        self.id = id

    def __repr__(self):
        return "LispAST_Variable(%s)" % (self.id)

    def __str__(self):
        return "LispAST_Variable(%s)" % (self.id)

    def eval(self, env):
        val = env.get(self.id)
        if val:
            return LispEvalContext(env, val)
        else:
            print("[LispEvalError]: Unknown variable: %s" % self.id)
            return LispEvalContext(env, LispValueVoid())


class LispAST_Datum(LispAST):
    def __init__(self, content):
        self.content = content

    def __repr__(self):
        return "LispAST_Datum(%s)" % self.content

    def __str__(self):
        return "%s" % map(str, self.content)


class LispAST_Symbol(LispAST):
    def __init__(self, _, txt, __):
        self.text = txt

    def __repr__(self):
        return "LispAST_Symbol(%s)" % self.text

    def __str__(self):
        return self.text


class LispAST_List(LispAST):
    def __init__(self, head, tail):
        self.head = head
        self.tail = tail

    def __repr__(self):
        return "LispAST_List(%s, %s)" % (self.head, self.tail)

    def __str__(self):
        if self.tail:
            return "(%s . %s)" % (list(map(str, self.head)), str(self.tail))
        else:
            return "(%s)" % list(map(str, self.head))


class LispAST_Vector(LispAST):
    def __init__(self, content):
        self.content = content

    def __repr__(self):
        return "LispAST_Vector(%s)" % self.content

    def __str__(self):
        return "#(%s)" % list(map(str, self.content))


class LispAST_Abbreviation(LispAST):
    def __init__(self, abbrev, datum):
        self.abbrev = abbrev
        self.datum = datum

    def __repr__(self):
        return "LispAST_Abbreviation(%s, %s)" % (self.abbrev, self.datum)

    def __str__(self):
        return "%s%s" % (str(self.abbrev), str(self.datum))


class LispAST_Quotation(LispAST):
    def __init__(self, datum):
        self.datum = datum

    def __repr__(self):
        return "LispAST_Quotation(%s)" % (self.datum)

    def __str__(self):
        return "'%s" % str(self.datum)

    def eval(self, env):
        datumValueType = False
        if isinstance(self.datum, LispAST_Vector):
            datumValueType = LispValueTypes.Vector
        elif isinstance(self.datum, LispAST_List):
            datumValueType = LispValueTypes.Pair
        elif isinstance(self.datum, LispAST_Symbol):
            datumValueType = LispValueTypes.Symbol
        elif isinstance(self.datum, LispAST_Abbreviation):
            datumValueType = LispValueTypes.Pair  # hmm not sure here
        elif isinstance(self.datum, LispAST_token):
            if self.datum.tokenType == LispTokenTypes.Boolean:
                datumValueType = LispValueTypes.Boolean
            elif self.datum.tokenType == LispTokenTypes.Number:
                datumValueType = LispValueTypes.Number
            elif self.datum.tokenType == LispTokenTypes.Character:
                datumValueType = LispValueTypes.Character
            elif self.datum.tokenType == LispTokenTypes.String:
                datumValueType = LispValueTypes.String
            else:
                raise Exception("Unexpected simple datum token type: %s" % self.datum.tokenType)
        else:
            raise Exception("Unexpected datum type: %s" % type(self.datum).__name__)

        return LispEvalContext(env, LispValue(self.datum, datumValueType))


class LispAST_ProcedureCall(LispAST):
    def __init__(self, operator, operands):
        self.operator = operator
        self.operands = operands

    def __repr__(self):
        return "LispAST_ProcedureCall(%s, %s)" % (self.operator, self.operands)

    def __str__(self):
        return "(%s, %s)" % (self.operator, self.operands)

    def eval(self, env):
        fun = self.operator.eval(env)
        if not fun or (fun.value.valueType != LispValueTypes.Procedure
                       and fun.value.valueType != LispValueTypes.Primitive):
            print("[LispEvalError] Invalid procedure call operator: %s" % self.operator)
            return LispValueVoid()

        args = list(map(lambda x: x.eval(env).value, self.operands))
        funAst = fun.value.value  # context -> value -> proc

        if fun.value.valueType == LispValueTypes.Primitive:
            return funAst.apply(args)

        else:  # LispValueTypes.Procedure
            newEnv = fun.env.copy()
            if funAst.formals.varlist:
                newEnv[funAst.formals.varlist.id] = LispValue(LispAST_List(args, False), LispValueTypes.Pair)
            else:
                hasRest = funAst.formals.rest
                varsCount = len(funAst.formals.vars)
                validArgNum = (len(args) >= varsCount) if hasRest else (len(args) == varsCount)
                if not validArgNum:
                    print("[LispEvalError] Invalid argment count for %s. Expecting %d, got %d."
                          % (self.operator, varsCount, len(args)))
                    return LispValueVoid()
                for i in range(varsCount):
                    newEnv[funAst.formals.vars[i].id] = args[i]
                if hasRest:
                    newEnv[funAst.formals.rest.id] = LispValue(LispAST_List(args[varsCount:], False),
                                                               LispValueTypes.Pair)

            bodyValue = funAst.body.eval(newEnv)
            return LispEvalContext(env, bodyValue.value)


class LispAST_Formals(LispAST):
    def __init__(self, varlist, vars, rest):
        self.varlist = varlist
        self.vars = vars
        self.rest = rest

    def __repr__(self):
        return "LispAST_Formals(%s,%s,%s)" % (self.varlist, self.vars, self.rest)

    def __str__(self):
        return "LispAST_Formals(%s,%s,%s)" % (self.varlist, self.vars, self.rest)


class LispAST_Body(LispAST):
    def __init__(self, definitions, body):
        self.definitions = definitions
        self.body = body

    def __repr__(self):
        return "LispAST_Body(%s,%s)" % (self.definitions, self.body)

    def __str__(self):
        return "LispAST_Body(%s,%s)" % (self.definitions, self.body)

    def eval(self, env):
        newEnv = env.copy()
        for i in range(len(self.definitions)):
            newEnv = self.definitions[i].eval(newEnv).env

        currentVal = LispValueVoid()

        for b in range(len(self.body)):
            currentVal = self.body[b].eval(newEnv)
            newEnv = currentVal.env
        return LispEvalContext(newEnv, currentVal.value)


class LispAST_LambdaExpression(LispAST):
    def __init__(self, formals, body):
        self.formals = formals
        self.body = body

    def __repr__(self):
        return "LispAST_LambdaExpression(%s,%s)" % (self.formals, self.body)

    def __str__(self):
        return "LispAST_LambdaExpression(%s,%s)" % (self.formals, self.body)

    def eval(self, env):
        return LispEvalContext(env, LispValue(self, LispValueTypes.Procedure, env.copy()))


class LispAST_Primitive(LispAST):
    def __init__(self, name, pyFun, argCount=False):
        self.name = name
        self.pyFun = pyFun
        self.argCount = argCount

    def __repr__(self):
        return "LispAST_Primitive(%s,%s)" % (self.name, self.argCount)

    def __str__(self):
        return "LispAST_Primitive(%s,%s)" % (self.name, self.argCount)

    def eval(self, env):
        return LispEvalContext(env, LispValue(self, LispValueTypes.Primitive))

    def apply(self, args):
        validArgNum = (len(args) == self.argCount) if self.argCount else True
        if not validArgNum:
            print("[LispEvalError] Invalid argment count for primitive %s. Expecting %d, got %d."
                  % (self.name, self.argCount, len(args)))
            return LispEvalContext([], LispValueVoid())
        else:
            return LispEvalContext([], self.pyFun(*args))


def lispIsFalse(val):
    return val.valueType == LispValueTypes.Boolean and not val.value


class LispAST_Conditional(LispAST):
    def __init__(self, test, consequent, alternate):
        self.test = test
        self.consequent = consequent
        self.alternate = alternate

    def __repr__(self):
        return "LispAST_Conditional(%s,%s,%s)" % (self.test, self.consequent, self.alternate)

    def __str__(self):
        return "LispAST_Conditional(%s,%s,%s)" % (self.test, self.consequent, self.alternate)

    def eval(self, env):
        testVal = self.test.eval(env).value
        isFalse = lispIsFalse(testVal)
        if not isFalse:
            return self.consequent.eval(env)
        else:
            return self.alternate.eval(env)


class LispAST_Assignement(LispAST):
    def __init__(self, var, exp):
        self.var = var
        self.exp = exp

    def __repr__(self):
        return "LispAST_Assignement(%s,%s)" % (self.var, self.exp)

    def __str__(self):
        return "LispAST_Assignement(%s,%s)" % (self.var, self.exp)

    def eval(self, env):
        newEnv = env.copy()
        expValue = self.exp.eval(newEnv)
        newEnv[self.var.id] = expValue.value
        return LispEvalContext(newEnv, LispValueVoid())


class LispAST_Definition:
    def __init__(self, var, body):
        self.var = var
        self.body = body

    def __repr__(self):
        return "LispAST_Definition(%s,%s)" % (self.var, self.body)

    def __str__(self):
        return "LispAST_Definition(%s,%s)" % (self.var, self.body)


class LispAST_Begin:
    def __init__(self, body):
        self.body = body

    def __repr__(self):
        return "LispAST_Begin(%s)" % (self.body)

    def __str__(self):
        return "LispAST_Begin(%s)" % (self.body)

    def eval(self, env):
        newEnv = env.copy()
        val = LispValueVoid()
        for i in range(len(self.body)):
            res = self.body[i].eval(newEnv)
            newEnv, val = res.env, res.value
        return LispEvalContext(newEnv, val)


class LispAST_CondClause:
    def __init__(self, test, body, isAlternateForm):
        self.test = test
        self.body = body
        self.isAlternateForm = isAlternateForm

    def __repr__(self):
        return "LispAST_CondClause(%s,%s,%s)" % (self.test, self.body, self.isAlternateForm)

    def __str__(self):
        return "LispAST_CondClause(%s,%s,%s)" % (self.test, self.body, self.isAlternateForm)

    def eval(self, env):
        testVal = self.test.eval(env).value
        isFalse = lispIsFalse(testVal)
        if isFalse:
            return False
        elif self.isAlternateForm:
            funVal = self.body.eval(env).value
            if (funVal.valueType != LispValueTypes.Procedure
                    or len(funVal.value.formals.vars) != 1):
                print("[LispEvalError] Invalid alternate cond clause: %s" % (self.body))
                return LispEvalContext(env, LispValueVoid())
            return LispAST_ProcedureCall(funVal.value, [testVal.value]).eval(env)
        else:
            val = LispValueVoid()
            for e in self.body:
                val = e.eval(env)
            return val


class LispAST_Cond:
    def __init__(self, clauses, elseClause):
        self.clauses = clauses
        self.elseClause = elseClause

    def __repr__(self):
        return "LispAST_Cond(%s, %s)" % (self.clauses, self.elseClause)

    def __str__(self):
        return "LispAST_Cond(%s, %s)" % (self.clauses, self.elseClause)

    def eval(self, env):
        for clause in self.clauses:
            clauseVal = clause.eval(env)
            if clauseVal:
                return clauseVal
        if self.elseClause:
            val = LispValueVoid()
            for e in self.elseClause:
                val = e.eval(env)
            return val
        else:
            return LispEvalContext(env, LispValueVoid())


class LispAST_Binding:
    def __init__(self, var, expr):
        self.var = var
        self.expr = expr

    def __repr__(self):
        return "LispAST_Binding(%s,%s)" % (self.var, self.expr)

    def __str__(self):
        return "LispAST_Binding(%s,%s)" % (self.var, self.expr)


class LispAST_Let:
    def __init__(self, bindings, body, isSeq=False, isRec=False):
        self.bindings = bindings
        self.body = body
        self.isSeq = isSeq
        self.isRec = isRec

    def __repr__(self):
        return "LispAST_Let(%s,%s,%s,%s)" % (self.bindings, self.body, self.isSeq, self.isRec)

    def __str__(self):
        return "LispAST_Let(%s,%s,%s,%s)" % (self.bindings, self.body, self.isSeq, self.isRec)

    def eval(self, env):
        newEnv = env.copy()

        if self.isRec:
            for i in range(len(self.bindings)):
                var = self.bindings[i].var.id
                newEnv[var] = False
            for i in range(len(self.bindings)):
                var = self.bindings[i].var.id
                val = self.bindings[i].expr.eval(newEnv).value
                newEnv[var] = val
        else:
            for i in range(len(self.bindings)):
                if self.isSeq:
                    var = self.bindings[i].var.id
                    val = self.bindings[i].expr.eval(newEnv).value
                    newEnv[var] = val
                else:  # normal let case
                    var = self.bindings[i].var.id
                    val = self.bindings[i].expr.eval(env).value
                    newEnv[var] = val

        return self.body.eval(newEnv)


class LispAST_andOr:
    def __init__(self, tests, isAnd):
        self.tests = tests
        self.isAnd = isAnd

    def __repr__(self):
        return "LispAST_andOr(%s,%s)" % (self.tests, self.isAnd)

    def __str__(self):
        return "LispAST_andOr(%s,%s)" % (self.tests, self.isAnd)

    def eval(self, env):
        for i in range(len(self.tests)):
            testVal = self.tests[i].eval(env).value
            isFalse = lispIsFalse(testVal)
            if (self.isAnd and isFalse):
                return LispEvalContext(env, lispMakeBoolValue(False))
            elif (not self.isAnd) and (not isFalse):
                return LispEvalContext(env, testVal)
        return LispEvalContext(env, lispMakeBoolValue(True if self.isAnd else False))


###############################################################################
## Lexing

class LexResult:
    def __init__(self, token, rest, extra=False, pos=0):
        self.result = token
        self.rest = rest
        self.extra = extra
        self.pos = 0

    def __repr__(self):
        return "LexResult(\"%s\", \"%s\", %s)" % (self.result, self.rest, self.extra)


def lexGeneric0(str, fn):
    if len(str) == 0:
        return False
    isLetter = fn(str[0])
    if isLetter:
        return LexResult(str[0], str[1:])
    else:
        return False


def lexCompose(str, fns, init=""):
    if LispLexerDebug: print("lexCompose(%s, %s, %s)" % (str, fns, init))
    if len(fns) == 0:
        return LexResult(init, str)
    else:
        res = fns[0](str)
        if res:
            comp = lexCompose(res.rest, fns[1:], init)
            if comp:
                return LexResult(res.result + comp.result, comp.rest)
            else:
                return False
        else:
            return False


def lexWord(str, word):
    if LispLexerDebug: print("lexWord(%s, %s)" % (str, word))
    wordLen = len(word)
    if str[0:wordLen] == word:
        return LexResult(word, str[wordLen:])
    else:
        return False


def lexMultiple(str, minCount, fn, init=""):
    if LispLexerDebug: print("lexMultiple(%s, %s, %s, %s)" % (str, minCount, fn, init))
    count = 0
    result = LexResult(init, str)

    while True:
        currentResult = fn(result.rest)
        # print("str: %s result: %s" % ((result.rest if result else False), result))
        if currentResult:
            count = count + 1
            result.result = result.result + currentResult.result
            result.rest = currentResult.rest
            if not currentResult.rest:
                break  # finished
        else:
            break

    # print("count: %d >= %d" % (count ,minCount))
    if count >= minCount:
        return result
    else:
        return False


def lexComment(str):
    if LispLexerDebug: print("lexComment(%s)" % str)
    length = len(str)
    if length == 0 or str[0] != ';':
        return False
    outStrIndex = length
    for i in range(length):
        if str[i] == '\n':
            outStrIndex = i + 1
            break
    return LexResult(str[0:outStrIndex], str[outStrIndex:])


def lexWhitespace(str):
    if LispLexerDebug: print("lexWhitespace(%s)" % str)
    spaces = [' ', '\t', '\n', '\r']
    end = len(str)
    for i in range(end):
        if str[i] not in spaces:
            end = i
            break
    if end == 0:
        return False
    else:
        return LexResult(str[0:end], str[end:])


def lexDelimiter(str):
    if LispLexerDebug: print("lexDelimiter(%s)" % str)
    simpleDelmiters = ['|', '(', ')', '"', ';']
    return (lexGeneric0(str, lambda chr: chr in simpleDelmiters)
            or lexWhitespace(str))


def lexAtmosphere(str):
    if LispLexerDebug: print("lexAtmosphere(%s)" % str)
    return lexWhitespace(str) or lexComment(str)


def lexInterTokenSpace(str):
    if LispLexerDebug: print("lexInterTokenSpace(%s)" % str)
    return lexMultiple(str, 0, lexAtmosphere)


def lexLetter(str):
    if LispLexerDebug: print("lexLetter(%s)" % str)
    return lexGeneric0(str, lambda chr: ((chr >= 'a' and chr <= 'z')
                                         or (chr >= 'A' and chr <= 'Z')))


def lexSpecialInitial(str):
    if LispLexerDebug: print("lexSpecialInitial(%s)" % str)
    specialChars = ['!', '$', '%', '&', '*', '/', ':',
                    '<', '=', '>', '?', '^', '_', '-', '~']
    return lexGeneric0(str, lambda chr: chr in specialChars)


def lexDigit(str, base=10):
    if LispLexerDebug: print("lexDigit(%s, %s)" % (str, base))
    if base == 16:
        return (lexGeneric0(str, lambda c: c >= '0' and c <= '9')
                or lexGeneric0(str, lambda c: c >= 'A' and c <= 'F')
                or lexGeneric0(str, lambda c: c >= 'a' and c <= 'f'))
    else:
        return lexGeneric0(str, lambda c: c >= '0' and c < chr(ord('0') + base))


def lexSpecialSubsequent(str):
    if LispLexerDebug: print("lexSubsequent(%s)" % str)
    chars = ['+', '-', '.', '@']
    return lexGeneric0(str, lambda chr: chr in chars)


def lexPeculiarIdentifier(str):
    if LispLexerDebug: print("lexPeculiarIdentifier(%s)" % str)
    chars = ['+', '-']  # missing '...'
    char = lexGeneric0(str, lambda chr: chr in chars)
    if char:
        return char

    return lexWord(str, '...')


def lexInitial(str):
    if LispLexerDebug: print("lexInitial(%s)" % str)
    return lexLetter(str) or lexSpecialInitial(str)


def lexSubsequent(str):
    if LispLexerDebug: print("lexSubsequent(%s)" % str)
    return lexInitial(str) or lexDigit(str) or lexSpecialSubsequent(str)


def lexIdentifier(str):
    if LispLexerDebug: print("lexIdentifier(%s)" % str)
    iniRes = lexInitial(str)
    if iniRes:
        subs = lexMultiple(iniRes.rest, 0, lexSubsequent)
        return (LexResult(iniRes.result + subs.result, subs.rest) if subs else False)
    else:
        return lexPeculiarIdentifier(str)


def lexExpressionKeyword(str):
    if LispLexerDebug: print("lexExpressionKeyword(%s)" % str)
    return (lexWord(str, "quote")
            or lexWord(str, "lambda")
            or lexWord(str, "if")
            or lexWord(str, "set!")
            or lexWord(str, "begin")
            or lexWord(str, "cond")
            or lexWord(str, "and")
            or lexWord(str, "or")
            or lexWord(str, "case")
            or lexWord(str, "let")
            or lexWord(str, "let*")
            or lexWord(str, "letrec")
            or lexWord(str, "do")
            or lexWord(str, "delay")
            or lexWord(str, "quasiquote"))


def lexSynacticKeyword(str):
    if LispLexerDebug: print("lexSynacticKeyword(%s)" % str)
    return (lexExpressionKeyword(str)
            or lexWord(str, "else")
            or lexWord(str, "=>")
            or lexWord(str, "define")
            or lexWord(str, "unquote")
            or lexWord(str, "unquote-splicing"))


# def lexVariable(str):
#     if LispLexerDebug : print("lexVariable(%s)" % str)
#     if not lexSynacticKeyword(str):
#         return lexIdentifier(str)
#     else:
#         return False

def lexBoolean(str):
    if LispLexerDebug: print("lexBoolean(%s)" % str)
    if lexWord(str, "#t"):
        return LexResult("#t", str[2:], True)
    elif lexWord(str, "#f"):
        return LexResult("#f", str[2:], False)
    else:
        return False


def lexAnyCharacter(str):
    if LispLexerDebug: print("lexAnyCharacter(%s)" % str)
    return lexGeneric0(str, lambda x: True)


def lexSpecificCharacter(str, c):
    if LispLexerDebug: print("lexSpecificCharacter(%s, %s)" % (str, c))
    return lexGeneric0(str, lambda x: x == c)


def lexCharacterName(str):
    if LispLexerDebug: print("lexCharacterName(%s)" % str)
    return lexWord(str, "space") or lexWord(str, "newline") or lexWord(str, "tab")


def lexCharacter(str):
    if LispLexerDebug: print("lexCharacter(%s)" % str)
    init = lexWord(str, "#\\")
    if (init):
        res = lexCharacterName(init.rest) or lexAnyCharacter(init.rest)
        if res:
            return LexResult("#\\" + res.result, res.rest, res.result)
        else:
            return False
    else:
        return False


def lexStringElement(str):
    if LispLexerDebug: print("lexStringElement(%s)" % str)
    res = lexWord(str, "\\\"") or lexWord(str, "\\\\")
    if res:
        return res
    else:
        any = lexAnyCharacter(str)
        if any.result != "\"" and any.result != "\\":
            return any
        else:
            return False


def lexString(str):
    if LispLexerDebug: print("lexString(%s)" % str)
    init = lexSpecificCharacter(str, '"')
    if init:
        content = lexMultiple(init.rest, 0, lexStringElement)
        if content and lexSpecificCharacter(content.rest, '"'):
            return LexResult("\"" + content.result + "\"", content.rest[1:], content.result)
        else:
            return False
    else:
        return False


def lexEmpty(str):
    if LispLexerDebug: print("lexEmpty(%s)" % str)
    return LexResult("", str)


###############################################################################
## Number lex / tokens

class container:
    def __init__(self, content=False):
        self.content = content


def assignContainer(res, varCont, fn=lambda x: x):
    if res and varCont:
        varCont.content = fn(res.extra)
    return res


def lexSign(str):
    if LispLexerDebug: print("lexSign(%s)" % str)
    sign = container(1)
    result = (lexSpecificCharacter(str, "+")
              or assignContainer(lexSpecificCharacter(str, "-"), sign, lambda x: -1)
              or lexEmpty(str))
    result.extra = sign.content
    return result


def lexUInteger(str, base):
    if LispLexerDebug: print("lexUInteger(%s, %s)" % (str, base))
    result = lexCompose(str, [lambda x: lexMultiple(x, 1, lambda y: lexDigit(y, base)),
                              lambda x: lexMultiple(x, 0, lambda y: lexSpecificCharacter(y, "#"))])
    if result:
        result.extra = result.result
        return result
    else:
        return False


def lexRadix(str, base, numAST):
    if LispLexerDebug: print("lexRadix(%s, %s)" % (str, base))
    if base == 2:
        numAST.base = 2
        return lexWord(str, "#b")
    elif base == 8:
        numAST.base = 8
        return lexWord(str, "#o")
    elif base == 10:
        numAST.base = 10
        return lexWord(str, "#d")  # or lexEmpty(str)
    elif base == 16:
        numAST.base = 16
        return lexWord(str, "#x")


def lexExponentMarker(str):
    if LispLexerDebug: print("lexExponentMarker(%s)" % (str))
    markers = "esfdl"
    return lexGeneric0(str, lambda chr: chr in markers)


def lexExactness(str, numAST):
    if LispLexerDebug: print("lexExactness(%s)" % (str))
    isExact = container(True)
    result = (assignContainer(lexWord(str, "#i"), isExact, lambda x: False)
              or assignContainer(lexWord(str, "#e"), isExact, lambda x: True))  # or lexEmpty(str)
    numAST.exactness = isExact.content
    return result


def lexNumberPrefix(str, base, numAST):
    if LispLexerDebug: print("lexNumberPrefix(%s, %s)" % (str, base))
    return (lexCompose(str, [lambda x: lexRadix(x, base, numAST),
                             lambda x: lexExactness(x, numAST)])
            or lexCompose(str, [lambda x: lexExactness(x, numAST),
                                lambda x: lexRadix(x, base, numAST)])
            or lexRadix(str, base, numAST)
            # base 10 can omit the radix
            or (base == 10) and (lexExactness(str, numAST)
                                 or lexEmpty(str)))


def lexNumberSuffix(str, allowsEmpty=True):
    if LispLexerDebug: print("lexNumberSuffix(%s)" % (str))
    return (lexCompose(str, [lexExponentMarker,
                             lexSign,
                             lambda x: lexMultiple(x, 1, lexDigit)])
            or (allowsEmpty and lexEmpty(str)))


def lexDecimal(str):
    if LispLexerDebug: print("lexDecimal(%s)" % (str))
    result = (lexCompose(str, [lambda x: lexMultiple(x, 1, lexDigit),
                               lambda x: lexMultiple(x, 1, lambda y: lexSpecificCharacter(y, "#")),
                               lambda x: lexSpecificCharacter(x, "."),
                               lambda x: lexMultiple(x, 0, lambda y: lexSpecificCharacter(y, "#")),
                               lexNumberSuffix])
              or lexCompose(str, [lambda x: lexSpecificCharacter(x, "."),
                                  lambda x: lexMultiple(x, 1, lexDigit),
                                  lambda x: lexMultiple(x, 0, lambda y: lexSpecificCharacter(y, "#")),
                                  lexNumberSuffix])
              or lexCompose(str, [lambda x: lexMultiple(x, 1, lexDigit),
                                  lambda x: lexSpecificCharacter(x, "."),
                                  lambda x: lexMultiple(x, 1, lexDigit),
                                  lambda x: lexMultiple(x, 0, lambda y: lexSpecificCharacter(y, "#")),
                                  lexNumberSuffix])
              or lexCompose(str, [lambda x: lexUInteger(x, 10),
                                  lambda x: lexNumberSuffix(x, False)]))
    if result:
        result.extra = result.result
        return result
    else:
        return False


def lexURealNumber(str, base):
    def toInt(n):
        if base == 10:
            # print("toInt(%s, %s): %d" % (n, base, int(float(n))))
            return int(float(n))
        else:
            # print("toInt(%s, %s): %d" % (n, base, int(n, base)))
            return int(n, base)

    def toFloat(n):
        # print("toFloat(%s): %.2f" %(n, float(n)))
        return float(n)

    if LispLexerDebug: print("lexURealNumber(%s, %s)" % (str, base))

    numerator = container()
    denominator = container(1)

    result = (lexCompose(str, [lambda x: assignContainer(lexUInteger(x, base), numerator, toInt),
                               lambda x: lexSpecificCharacter(x, "/"),
                               lambda x: assignContainer(lexUInteger(x, base), denominator, toInt)])
              or (base == 10 and assignContainer(lexDecimal(str), numerator, toFloat))
              or assignContainer(lexUInteger(str, base), numerator, toInt))

    if result:
        result.extra = LispAST_Real(1, numerator.content, denominator.content, result.result)
        return result
    else:
        return False


def lexRealNumber(str, base):
    if LispLexerDebug: print("lexRealNumber(%s, %s)" % (str, base))

    signResult = lexSign(str)
    if not signResult:
        return False

    realResult = lexURealNumber(signResult.rest, base)
    if not realResult:
        return False

    realResult.result = signResult.result + realResult.extra.text
    realResult.extra.text = realResult.result
    realResult.extra.sign = signResult.extra
    return realResult


def lexNumberComplex(str, base, numAST):
    def inverse(n):
        n.sign = -1 * n.sign
        return n

    if LispLexerDebug: print("lexNumberComplex(%s, %s)" % (str, base))

    real = container(LispAST_Real(1, 0, 1, "0.0"))
    imag = container(LispAST_Real(1, 0, 1, "0.0"))
    isPolar = container(False)

    def reset(real, imag, isPolar):
        real.content = LispAST_Real(1, 0, 1, "0.0")
        imag.content = LispAST_Real(1, 0, 1, "0.0")
        isPolar.content = False
        return False

    result = (lexCompose(str, [lambda x: assignContainer(lexRealNumber(x, base), real),
                               lambda x: assignContainer(lexSpecificCharacter(x, "@"), isPolar),
                               lambda x: assignContainer(lexRealNumber(x, base), imag)])
              or reset(real, imag, isPolar)
              or lexCompose(str, [lambda x: assignContainer(lexRealNumber(x, base), real),
                                  lambda x: lexSpecificCharacter(x, "+"),
                                  lambda x: assignContainer(lexURealNumber(x, base), imag),
                                  lambda x: lexSpecificCharacter(x, "i")])
              or reset(real, imag, isPolar)
              or lexCompose(str, [lambda x: assignContainer(lexRealNumber(x, base), real),
                                  lambda x: lexSpecificCharacter(x, "-"),
                                  lambda x: assignContainer(lexURealNumber(x, base), imag, inverse),
                                  lambda x: lexSpecificCharacter(x, "i")])
              or reset(real, imag, isPolar)
              or lexCompose(str, [lambda x: assignContainer(lexRealNumber(x, base), real),
                                  lambda x: lexSpecificCharacter(x, "+"),
                                  lambda x: assignContainer(lexSpecificCharacter(x, "i"), imag,
                                                            lambda y: LispAST_Real(1, 1, 1, ""))])
              or reset(real, imag, isPolar)
              or lexCompose(str, [lambda x: assignContainer(lexRealNumber(x, base), real),
                                  lambda x: lexSpecificCharacter(x, "-"),
                                  lambda x: assignContainer(lexSpecificCharacter(x, "i"), imag,
                                                            lambda y: LispAST_Real(-1, 1, 1, ""))])
              or reset(real, imag, isPolar)
              or lexCompose(str, [lambda x: lexSpecificCharacter(x, "+"),
                                  lambda x: lexURealNumber(x, base),
                                  lambda x: assignContainer(lexSpecificCharacter(x, "i"), imag)])
              or reset(real, imag, isPolar)
              or lexCompose(str, [lambda x: lexSpecificCharacter(x, "-"),
                                  lambda x: assignContainer(lexURealNumber(x, base), imag, inverse),
                                  lambda x: lexSpecificCharacter(x, "i")])
              or reset(real, imag, isPolar)
              or lexCompose(str, [lambda x: lexSpecificCharacter(x, "+"),
                                  lambda x: assignContainer(lexSpecificCharacter(x, "i"), imag,
                                                            lambda y: LispAST_Real(1, 1, 1, ""))])
              or reset(real, imag, isPolar)
              or lexCompose(str, [lambda x: lexSpecificCharacter(x, "-"),
                                  lambda x: assignContainer(lexSpecificCharacter(x, "i"), imag,
                                                            lambda y: LispAST_Real(-1, 1, 1, ""))])
              or reset(real, imag, isPolar)
              or assignContainer(lexRealNumber(str, base), real)
              or reset(real, imag, isPolar))

    if result:
        # todo polar form
        numAST.real = real.content
        numAST.imag = imag.content
        numAST.text = result.result
        return result
    else:
        return False


def lexNumberBase(str, base, numAST):
    if LispLexerDebug: print("lexNumberBase(%s, %s)" % (str, base))
    return lexCompose(str, [lambda x: lexNumberPrefix(x, base, numAST),
                            lambda x: lexNumberComplex(x, base, numAST)])


def lexNumber(str):
    if LispLexerDebug: print("lexNumber(%s)" % (str))
    numAST = LispAST_Number()
    result = (lexNumberBase(str, 10, numAST)
              or lexNumberBase(str, 2, numAST)
              or lexNumberBase(str, 16, numAST)
              or lexNumberBase(str, 8, numAST))
    if result:
        isExact = (isinstance(numAST.real.numerator, int)
                   and isinstance(numAST.real.denominator, int)
                   and isinstance(numAST.imag.numerator, int)
                   and isinstance(numAST.imag.denominator, int))
        # print("test: %s %s" % (numAST.real.__repr__(), numAST.imag.__repr__()))
        if numAST.exactness and (not isExact):
            numAST.exactness = isExact  # todo: transform into exact instead of downcasting
        result.extra = numAST
        return result
    else:
        return False


class LispTokenTypes(IntEnum):
    Identifier = 0
    Boolean = 1
    Number = 2
    Character = 3
    String = 4
    LParen = 5
    RParen = 6
    SharpLParen = 7
    Quote = 8
    BackQuote = 9
    Comma = 10
    CommaSplice = 11
    Dot = 12
    StandartProcedure = 13
    SpecialForm = 14  # define, macro...


def tokenTypeToValue(tokenType):
    if tokenType == LispTokenTypes.Boolean:
        return LispValueTypes.Boolean
    elif tokenType == LispTokenTypes.Character:
        return LispValueTypes.Char
    elif tokenType == LispTokenTypes.Number:
        return LispValueTypes.Number
    elif tokenType == LispTokenTypes.String:
        return LispValueTypes.String
    else:
        raise Exception("Token type: '%s' is not self evaluating...", self.tokenType)


class LispToken:
    def __init__(self, tokenType, text, extra=[]):
        self.tokenType = tokenType
        self.text = text
        self.extra = extra

    def __repr__(self):
        return "LispToken(%s, \"%s\", %s)" % (self.tokenType, self.text, self.extra)


def lexToken(str):
    if LispLexerDebug: print("lexToken(%s)" % (str))

    lex = lexNumber(str)
    if lex:
        return LexResult(LispToken(LispTokenTypes.Number, lex.result, lex.extra), lex.rest)

    lex = lexIdentifier(str)
    if lex:
        return LexResult(LispToken(LispTokenTypes.Identifier, lex.result), lex.rest)

    lex = lexBoolean(str)
    if lex:
        return LexResult(LispToken(LispTokenTypes.Boolean, lex.result, lex.extra), lex.rest)

    lex = lexCharacter(str)
    if lex:
        return LexResult(LispToken(LispTokenTypes.Character, lex.result, lex.extra), lex.rest)

    lex = lexString(str)
    if lex:
        return LexResult(LispToken(LispTokenTypes.String, lex.result, lex.extra), lex.rest)

    lex = lexSpecificCharacter(str, "(")
    if lex:
        return LexResult(LispToken(LispTokenTypes.LParen, lex.result), lex.rest)

    lex = lexSpecificCharacter(str, ")")
    if lex:
        return LexResult(LispToken(LispTokenTypes.RParen, lex.result), lex.rest)

    lex = lexWord(str, "#(")
    if lex:
        return LexResult(LispToken(LispTokenTypes.SharpLParen, lex.result), lex.rest)

    lex = lexSpecificCharacter(str, "'")
    if lex:
        return LexResult(LispToken(LispTokenTypes.Quote, lex.result), lex.rest)

    lex = lexSpecificCharacter(str, "`")
    if lex:
        return LexResult(LispToken(LispTokenTypes.BackQuote, lex.result), lex.rest)

    lex = lexWord(str, ",@")
    if lex:
        return LexResult(LispToken(LispTokenTypes.CommaSplice, lex.result), lex.rest)

    lex = lexSpecificCharacter(str, ",")
    if lex:
        return LexResult(LispToken(LispTokenTypes.Comma, lex.result), lex.rest)

    lex = lexSpecificCharacter(str, ".")
    if lex:
        return LexResult(LispToken(LispTokenTypes.Dot, lex.result), lex.rest)

    return False  # failed parsing...


def parseTokens(str):
    tokens = []
    delimiterTokens = [LispTokenTypes.Identifier, LispTokenTypes.Number,
                       LispTokenTypes.Character, LispTokenTypes.Dot]
    input = str
    while True:
        space = lexInterTokenSpace(input)
        if space:
            input = space.rest

        lex = lexToken(input)

        if not lex:
            if not input:
                return tokens
            else:
                return False
        else:

            token = lex.result
            token.pos = str.index(lex.rest)

            input = lex.rest
            if token.tokenType in delimiterTokens:
                delim = lexDelimiter(input)
                if input and not delim:
                    return False
            tokens += [token]
    return tokens


###############################################################################
## Parsing

class ParseResult:
    def __init__(self, ast, rest):
        self.result = [ast]
        self.rest = rest
        self.extra = ast

    def __repr__(self):
        return "ParseResult(%s, %s)" % (self.result, self.rest)


def parseTokenType(tokens, tokenType, astType):
    if not tokens or len(tokens) == 0 or not isinstance(tokens[0], LispToken):
        return False
    if tokens[0].tokenType == tokenType:
        return ParseResult(astType(tokens[0].tokenType, tokens[0].text, tokens[0].extra), tokens[1:])
    else:
        return False


def parseTokenTypes(tokens, types, astType):
    if not tokens or len(tokens) == 0 or not isinstance(tokens[0], LispToken):
        return False
    if tokens[0].tokenType in types:
        return ParseResult(astType(tokens[0].tokenType, tokens[0].text, tokens[0].extra), tokens[1:])
    else:
        return False


def parseNumber(tokens):
    if not tokens or len(tokens) == 0 or not isinstance(tokens[0], LispToken):
        return False
    if tokens[0].tokenType == LispTokenTypes.Number:
        return ParseResult(tokens[0].extra, tokens[1:])
    else:
        return False


def cleanUpAsts(asts):
    def clean(a, x):
        if isinstance(x, LispAST_void):
            return a
        else:
            return a + [x]

    return functools.reduce(clean, asts, [])


def parseCompose(tokens, compFns, astType):
    if not tokens or (len(tokens) == 0 and len(compFns) > 0):
        return False

    result = lexCompose(tokens, compFns, init=[])
    if result:
        asts = result.result
        cleanAsts = cleanUpAsts(asts)
        # print("test: %s" % cleanAsts)
        return ParseResult(astType(*cleanAsts), result.rest)
    else:
        return False


def parseMultiple(tokens, n, fn):
    lexResult = lexMultiple(tokens, n, fn, init=[])
    if lexResult:
        asts = lexResult.result
        cleanAsts = cleanUpAsts(asts)
        return ParseResult(cleanAsts, lexResult.rest)
    else:
        return False


def parseSpecificIdentifier(tokens, id, isVoid=False):
    identifier = parseTokenType(tokens, LispTokenTypes.Identifier, LispAST_token)
    if not identifier or identifier.result[0].text != id:
        return False
    else:
        return identifier if not isVoid else ParseResult(LispAST_void(), identifier.rest)


def parseSExp(tokens, id, bodyParseList, astType, startToken=LispTokenTypes.LParen, endToken=LispTokenTypes.RParen):
    resOffset = 1
    if not parseTokenType(tokens, startToken, LispAST_token):
        return False

    if id != "":
        if not parseSpecificIdentifier(tokens[1:], id):
            return False
        else:
            resOffset = 2

    result = parseCompose(tokens[resOffset:], bodyParseList, astType)

    if not result:
        return False
    if parseTokenType(result.rest, endToken, LispAST_token):
        result.rest = result.rest[1:]
        return result
    else:
        return False


###############################################################################
## Datum Parsing (read)

def parseAbbrevPrefix(tokens):
    prefixTypes = [LispTokenTypes.Quote, LispTokenTypes.BackQuote,
                   LispTokenTypes.Comma, LispTokenTypes.CommaSplice]
    return parseTokenTypes(tokens, prefixTypes, LispAST_token)


def parseSymbol(tokens):
    return parseTokenType(tokens, LispTokenTypes.Identifier, LispAST_Symbol)


def parseSimpleDatum(tokens):
    simpleDatumTypes = [LispTokenTypes.Boolean, LispTokenTypes.Number,
                        LispTokenTypes.Character, LispTokenTypes.String]

    return parseTokenTypes(tokens, simpleDatumTypes, LispAST_token) or parseSymbol(tokens)


def parseList(tokens):
    return (parseSExp(tokens, "",
                      [lambda x: parseMultiple(x, 0, parseDatum)],
                      lambda x: LispAST_List(x, False))
            or parseSExp(tokens, "",
                         [lambda x: parseMultiple(x, 0, parseDatum),
                          lambda x: parseTokenType(x, LispTokenTypes.Dot, LispAST_void),
                          parseDatum],
                         LispAST_List))


def parseVector(tokens):
    return parseSExp(tokens, "",
                     [lambda x: parseMultiple(x, 0, parseDatum)],
                     LispAST_Vector,
                     startToken=LispTokenTypes.SharpLParen,
                     endToken=LispTokenTypes.RParen)


def parseAbbreviation(tokens):
    return parseCompose(tokens, [parseAbbrevPrefix, parseDatum], LispAST_Abbreviation)


def parseCompoundDatum(tokens):
    return parseList(tokens) or parseVector(tokens) or parseAbbreviation(tokens)


def parseDatum(tokens):
    return parseCompoundDatum(tokens) or parseSimpleDatum(tokens)


###############################################################################
## Expression Parsing

def parseQuotation(tokens):
    return (parseCompose(tokens, [lambda x: parseTokenType(x, LispTokenTypes.Quote, LispAST_void),
                                  parseDatum],
                         LispAST_Quotation)
            or parseSExp(tokens, "quote", [parseDatum], LispAST_Quotation))


def parseSelfEvaluating(tokens):
    return (parseTokenTypes(tokens, [LispTokenTypes.Boolean,
                                     LispTokenTypes.Character, LispTokenTypes.String],
                            LispAST_token)
            or parseNumber(tokens))


def parseLitteral(tokens):
    if LispLexerDebug: print("parseLitteral(%s)" % tokens)
    return parseQuotation(tokens) or parseSelfEvaluating(tokens)


def parseVariable(tokens):
    if LispLexerDebug: print("parseVariable(%s)" % tokens)
    id = parseTokenType(tokens, LispTokenTypes.Identifier, LispAST_token)
    if id:
        keyword = lexSynacticKeyword(id.result[0].text)
        if not keyword or keyword.result != id.result[0].text:
            return ParseResult(LispAST_Variable(id.result[0].text), id.rest)
        else:
            return False
    else:
        return False


def parseOperator(tokens):
    return parseExpression(tokens)


def parseOperands(tokens):
    return parseMultiple(tokens, 0, parseExpression)


def parseProcedureCall(tokens):
    if LispLexerDebug: print("parseProcedureCall(%s)" % tokens)
    return parseSExp(tokens, "", [parseOperator, parseOperands], LispAST_ProcedureCall)


def parseFormals(tokens):
    if LispLexerDebug: print("parseFormals(%s)" % tokens)
    return (parseSExp(tokens, "", [lambda x: parseMultiple(x, 0, parseVariable)],
                      lambda x: LispAST_Formals(False, x, False))
            or parseSExp(tokens, "", [lambda x: parseMultiple(x, 0, parseVariable),
                                      lambda x: parseTokenType(x, LispTokenTypes.Dot, LispAST_void),
                                      parseVariable],
                         lambda x, y: LispAST_Formals(False, x, y))
            or (lambda x: ParseResult(LispAST_Formals(x.result[0], False, False), x.rest) if x else False)(
                parseVariable(tokens)))


def parseCommand(tokens):
    return parseExpression(tokens);


def parseSequence(tokens):
    if LispLexerDebug: print("parseSequence(%s)" % tokens)
    return parseMultiple(tokens, 1, parseCommand)


def parseBody(tokens):
    if LispLexerDebug: print("parseBody(%s)" % tokens)
    return parseCompose(tokens, [lambda x: parseMultiple(x, 0, parseDefinition),
                                 parseSequence],
                        LispAST_Body)


def parseLambdaExpression(tokens):
    if LispLexerDebug: print("parseLambdaExpression(%s)" % tokens)
    return parseSExp(tokens, "lambda", [parseFormals, parseBody], LispAST_LambdaExpression)


def parseTest(tokens):
    if LispLexerDebug: print("parseTest(%s)" % tokens)
    return parseExpression(tokens)


def parseConsequent(tokens):
    if LispLexerDebug: print("parseConsequent(%s)" % tokens)
    return parseExpression(tokens)


def parseAlternate(tokens):
    if LispLexerDebug: print("parseAlternate(%s)" % tokens)
    return parseExpression(tokens) or ParseResult([False], tokens)  # or empty


def parseConditional(tokens):
    if LispLexerDebug: print("parseConditional(%s)" % tokens)
    return parseSExp(tokens, "if", [parseTest, parseConsequent, parseAlternate], LispAST_Conditional)


def parseAssignement(tokens):
    if LispLexerDebug: print("parseAssignement(%s)" % tokens)
    return parseSExp(tokens, "set!", [parseVariable, parseExpression], LispAST_Assignement)


def parseCondClause(tokens):
    return (parseSExp(tokens, "", [parseTest, parseSequence], lambda t, s: LispAST_CondClause(t, s, False))
            or parseSExp(tokens, "", [parseTest], lambda t: LispAST_CondClause(t, False, False))
            or parseSExp(tokens, "", [parseTest,
                                      lambda x: parseSpecificIdentifier(x, "=>", True),
                                      parseExpression],
                         lambda t, e: LispAST_CondClause(t, e, True)))


def parseBindingSpec(tokens):
    return parseSExp(tokens, "", [parseVariable, parseExpression], LispAST_Binding)


# def parseCaseClause(tokens):
#     return parseSExp(tokens, [lambda x: parseSExp(x, [lambda y: parseMultiple(y, 0, parseDatum)]),

#                               parseSequence])

# def parseIterationSpec(tokens):
#     return (parseSExp(tokens, [parseVariable, parseExpression, parseExpression])
#             or parseSExp(tokens, [parseVariable, parseExpression]))

# def parseDoResult(tokens):
#     return parseSequence(tokens) or LexResult([], tokens)

# def parseKeyword(tokens):
#     return parseTokenType(tokens, [LispTokenTypes.Identifier])

def parseDerivedExpression(tokens):
    if LispLexerDebug: print("parseDerivedExpression(%s)" % tokens)
    return (parseSExp(tokens, "cond", [lambda x: parseMultiple(x, 0, parseCondClause),
                                       lambda x: parseSExp(x, "else", [parseSequence], lambda x: x)],
                      lambda c, e: LispAST_Cond(c, e))
            or parseSExp(tokens, "cond", [lambda x: parseMultiple(x, 1, parseCondClause)],
                         lambda cs: LispAST_Cond(cs, False))

            or parseSExp(tokens, "let", [lambda x: parseSExp(x, "", [lambda y: parseMultiple(y, 0, parseBindingSpec)],
                                                             lambda bindings: bindings),
                                         parseBody],
                         lambda bindings, body: LispAST_Let(bindings, body, False, False))

            or parseSExp(tokens, "let*", [lambda x: parseSExp(x, "", [lambda y: parseMultiple(y, 0, parseBindingSpec)],
                                                              lambda bindings: bindings),
                                          parseBody],
                         lambda bindings, body: LispAST_Let(bindings, body, True, False))

            or parseSExp(tokens, "letrec",
                         [lambda x: parseSExp(x, "", [lambda y: parseMultiple(y, 0, parseBindingSpec)],
                                              lambda bindings: bindings),
                          parseBody],
                         lambda bindings, body: LispAST_Let(bindings, body, False, True))

            or parseSExp(tokens, "and", [lambda x: parseMultiple(x, 0, parseTest)],
                         lambda tests: LispAST_andOr(tests, True))

            or parseSExp(tokens, "or", [lambda x: parseMultiple(x, 0, parseTest)],
                         lambda tests: LispAST_andOr(tests, False))

            or parseSExp(tokens, "begin", [parseSequence], LispAST_Begin)

            # or parseSExp(tokens, "case",  [parseExpression,
            #                                lambda x: parseMultiple(x, 0, parseCaseClause),
            #                                lambda x: parseSExp(x, "else", [parseSequence])])
            or False)


#             or parseSExpWithId(tokens, "case",  [parseExpression,
#                                                  lambda x: lexMultiple(x, 0, parseCaseClause, init=[]),
#                                                  lambda x: parseSExpWithId(x, "else", [parseSequence])])
#             or parseSExpWithId(tokens, "case",  [parseExpression, lambda x: lexMultiple(x, 1, parseCaseClause, init=[])])

#             or parseSExpWithId(tokens, "do",    [lambda x: parseSExp(x, [lambda y: lexMultiple(y, 0, parseIterationSpec, init=[])]),
#                                                  lambda x: parseSExp(x, [parseTest, parseDoResult]),
#                                                  lambda x: lexMultiple(x, 0, parseExpression, init=[])])
#             or parseSExpWithId(tokens, "delay", [parseExpression])
#             or parseQuasiQuotation(tokens))

def parseMacroUse(tokens):
    return False


#     if LispLexerDebug : print("parseMacroUse(%s)" % tokens)
#     return parseSExp(tokens, [parseKeyword,
#                               lambda x: lexMultiple(x, 0, parseDatum, init=[])])
def parseMacroBlock(tokens):
    return False


#     if LispLexerDebug : print("parseMacroBlock(%s)" % tokens)
#     return (parseSExpWithId(tokens, "let-syntax",
#                             [lambda x: parseSExp(x, [lambda y: lexMultiple(y,
#                                                                            0,
#                                                                            parseSyntaxSpec,
#                                                                            init=[])]),
#                              parseBody])
#             or parseSExpWithId(tokens, "letrec-syntax",
#                             [lambda x: parseSExp(x, [lambda y: lexMultiple(y,
#                                                                            0,
#                                                                            parseSyntaxSpec,
#                                                                            init=[])]),
#                              parseBody]))

def parseExpression(tokens):
    if LispLexerDebug: print("parseExpression(%s)" % tokens)
    return (parseVariable(tokens)
            or parseLitteral(tokens)
            or parseDerivedExpression(tokens)
            or parseProcedureCall(tokens)
            or parseLambdaExpression(tokens)
            or parseConditional(tokens)
            or parseAssignement(tokens)
            or parseMacroUse(tokens)
            or parseMacroBlock(tokens))


def parseDefFormals(tokens):
    result = parseCompose(tokens, [lambda x: parseMultiple(x, 0, parseVariable),
                                   lambda x: parseTokenType(x, LispTokenTypes.Dot, LispAST_void),
                                   parseVariable],
                          lambda vars, rest: LispAST_Formals(False, vars, rest))
    if result:
        return result
    else:
        result = parseMultiple(tokens, 0, parseVariable)
        if result:
            return ParseResult(LispAST_Formals(False, result.result[0], False), result.rest)
        else:
            return False


def parseDefinition(tokens):
    if LispLexerDebug: print("parseDefinition(%s)" % tokens)
    var = container()
    formals = container()
    body = container()
    parsedResult = parseSExp(tokens, "define", [lambda x: assignContainer(parseVariable(x), var),
                                                lambda x: assignContainer(parseExpression(x), body)],
                             LispAST_void)
    if parsedResult:
        return ParseResult(LispAST_Assignement(var.content, body.content), parsedResult.rest)

    parsedResult = parseSExp(tokens, "define",
                             [lambda x: parseSExp(x, "", [lambda y: assignContainer(parseVariable(y), var),
                                                          lambda y: assignContainer(parseDefFormals(y), formals)],
                                                  LispAST_void),
                              lambda x: assignContainer(parseBody(x), body)],
                             LispAST_void)
    if parsedResult:
        return ParseResult(LispAST_Assignement(var.content, LispAST_LambdaExpression(formals.content, body.content)),
                           parsedResult.rest)

    parsedResult = parseSExp(tokens, "begin", [lambda x: parseMultiple(x, 0, parseDefinition)],
                             LispAST_Begin)
    return parsedResult


def parseSyntaxDefinition(tokens):
    if LispLexerDebug: print("parseSyntaxDefinition(%s)" % tokens)
    return False  # todo
    # return parseSExpWithId(tokens, "define-syntax", [parseKeyword, parseTransformerSpec])


def parseCommandOrDefinition(tokens):
    return (parseCommand(tokens)
            or parseDefinition(tokens)
            or parseSyntaxDefinition(tokens)
            or parseSExp(tokens, "begin", [lambda x: lexMultiple(x, 1, [parseCommandOrDefinition])],
                         LispAST_Begin))


def parseProgram(tokens):
    if LispLexerDebug: print("parseProgram(%s)" % tokens)
    return parseMultiple(tokens, 0, parseCommandOrDefinition)


# def parseSyntaxSpec(tokens):
#     # return parseSExp(tokens, [parseKeyword, parseTransformerSpec])
#     return False # todo...

# def parseQuasiQuotation(tokens):
#     if LispLexerDebug : print("parseQuasiQuotation(%s)" % tokens)
#     return False #todo

###############################################################################
## Evaluation and Values

class LispValueTypes(Enum):
    Boolean = 0
    Symbol = 1
    Char = 2
    Vector = 3
    Procedure = 4
    Pair = 5
    Number = 6
    String = 7
    Port = 8
    Primitive = 9
    Void = 10


class LispValue:
    def __init__(self, value, valueType, env=False):
        self.value = value
        self.valueType = valueType
        self.env = env

    def __repr__(self):
        return "LispValue(%s,%s)" % (self.value, self.valueType)

    def __str__(self):
        return "LispValue(%s,%s)" % (self.value, self.valueType)


def LispValueBool(b):
    return LispValue(LispAST_token(LispTokenTypes.Boolean, "#t" if b else "#f", b), LispValueTypes.Boolean)


def LispValueVoid():
    return LispValue(False, LispValueTypes.Void)


class LispEvalContext:
    def __init__(self, env, value):
        self.env = env
        self.value = value

    def __repr__(self):
        return "LispEvalContext(%s,%s)" % (self.env, self.value)

    def __str__(self):
        return "LispEvalContext(%s,%s)" % (self.env, self.value)


def lispMakePrimitive(id, pyFun):
    return LispValue(LispAST_Primitive(id, pyFun), LispValueTypes.Primitive)


def lispMakeBoolValue(val):
    return LispValue(val, LispValueTypes.Boolean)


def lispMakeString(val):
    return LispValue(LispAST_token(LispTokenTypes.String, val, val), LispValueTypes.String)


def lispMakeNumberValue(num, denom=1, imagNum=0, imagDenom=1):
    if np.isclose(denom, 1):
        denom = int(denom)
    if np.isclose(imagDenom, 1):
        imagDenom = int(imagDenom)

    isExact = (isinstance(num, int)
               and isinstance(denom, int)
               and isinstance(imagNum, int)
               and isinstance(imagDenom, int))

    if not isExact:
        realStr = "%.2f" % num if denom == 1 else "%.2f/%.2f" % (num, denom)
        imagStr = "" if imagNum == 0 else ("%.2f" % imagNum if imagDenom == 1 else "%.2f/%.2f" % (imagNum, imagDenom))
    else:
        realStr = "%d" % num if denom == 1 else "%d/%d" % (num, denom)
        imagStr = "" if imagNum == 0 else ("%d" % imagNum if imagDenom == 1 else "%d/%d" % (imagNum, imagDenom))

    numStr = "%s" % realStr if imagStr == "" else "%s + %si" % (realStr, imagStr)
    return LispValue(LispAST_Number(10, isExact,
                                    LispAST_Real(1, num, denom, realStr),
                                    LispAST_Real(1, imagNum, imagDenom, imagStr),
                                    numStr),
                     LispValueTypes.Number)


##-----------------------------------------------------------------------------
## primitive decorators

def allType(valType):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not all(v.valueType == valType for v in args):
                print("[LispEvalError] Invalid argument type passed to '%s'. Expecting type %s, got: %s"
                      % (func.__name__, valType, list(map(lambda v: v.valueType, args))))
                return LispEvalContext([], LispValueVoid())
            else:
                return func(*args, **kwargs)

        return wrapper

    return decorator


def primitivePrerequesite(primitive, typeStr):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not all(primitive(v).value for v in args):
                print("[LispEvalError] Invalid argument type passed to '%s'. Expecting %s, got: %s"
                      % (func.__name__, typeStr, list(map(lambda v: v.valueType, args))))
                return LispEvalContext([], LispValueVoid())
            else:
                return func(*args, **kwargs)

        return wrapper

    return decorator


def exactArgCount(count):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if len(args) != count:
                # print("[LispEvalError] Invalid argument count for '%s'. Expecting %d, got: %d"
                #       % (func.__name__, count, len(args)))
                # return LispEvalContext([], LispValueVoid())
                raise Exception("[LispEvalError] Invalid argument count for '%s'. Expecting %d, got: %d (%s)"
                                # % (func.__name__, count, len(args), list(map(lambda x: x.value, args))))
                                % (func.__name__, count, len(args), args))

            else:
                return func(*args, **kwargs)

        return wrapper

    return decorator


def minArgCount(count):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if len(args) < count:
                # print("[LispEvalError] Invalid argument count for '%s'. Expecting at least %d, got: %d"
                #       % (func.__name__, count, len(args)))
                raise Exception("[LispEvalError] Invalid argument count for '%s'. Expecting at least %d, got: %d"
                                % (func.__name__, count, len(args)))
                # return LispEvalContext([], LispValueVoid())
            else:
                return func(*args, **kwargs)

        return wrapper

    return decorator


class primitive:
    env = []

    def __init__(self, envId):
        self.envId = envId

    def __call__(self, prim):
        primitive.env = primitive.env + [(self.envId, prim)]
        return prim


##-----------------------------------------------------------------------------
## base type predicate procedures

@primitive("number?")
@exactArgCount(1)
def lispPrimitive_isNumber(*numbers):
    return lispMakeBoolValue(numbers[0].valueType == LispValueTypes.Number)


@primitive("pair?")
@exactArgCount(1)
def lispPrimitive_isPair(*numbers):
    return lispMakeBoolValue(numbers[0].valueType == LispValueTypes.Pair)


@primitive("char?")
@exactArgCount(1)
def lispPrimitive_isChar(*numbers):
    return lispMakeBoolValue(numbers[0].valueType == LispValueTypes.Char)


@primitive("string?")
@exactArgCount(1)
def lispPrimitive_isString(*numbers):
    return lispMakeBoolValue(numbers[0].valueType == LispValueTypes.String)


@primitive("boolean?")
@exactArgCount(1)
def lispPrimitive_isBoolean(*numbers):
    return lispMakeBoolValue(numbers[0].valueType == LispValueTypes.Boolean)


@primitive("symbol?")
@exactArgCount(1)
def lispPrimitive_isSymbol(*numbers):
    return lispMakeBoolValue(numbers[0].valueType == LispValueTypes.Symbol)


@primitive("vector?")
@exactArgCount(1)
def lispPrimitive_isVector(*numbers):
    return lispMakeBoolValue(numbers[0].valueType == LispValueTypes.Vector)


@primitive("procedure?")
@exactArgCount(1)
def lispPrimitive_isProcedure(*numbers):
    return lispMakeBoolValue(numbers[0].valueType == LispValueTypes.Procedure
                             or numbers[0].valueType == LispValueTypes.Primitive)


@primitive("port?")
@exactArgCount(1)
def lispPrimitive_isPort(*numbers):
    return lispMakeBoolValue(numbers[0].valueType == LispValueTypes.Port)


##-----------------------------------------------------------------------------
## number procedures

@primitive("complex?")
@exactArgCount(1)
def lispPrimitive_isComplex(*numbers):
    isComplex = numbers[0].valueType == LispValueTypes.Number
    return lispMakeBoolValue(isComplex)


@primitive("real?")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_isReal(*numbers):
    isReal = np.isclose(numbers[0].value.imag.numerator, 0.0)
    return lispMakeBoolValue(isReal)


@primitive("rational?")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_isRational(*numbers):
    isRational = (np.isclose(numbers[0].value.imag.numerator, 0.0)
                  and numbers[0].value.exactness)
    return lispMakeBoolValue(isRational)


@primitive("integer?")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_isInteger(*numbers):
    isInteger = (np.isclose(numbers[0].value.imag.numerator, 0.0)
                 and numbers[0].value.exactness
                 and np.isclose(numbers[0].value.real.denominator, 1.0))
    return lispMakeBoolValue(isInteger)


@primitive("exact?")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_isExact(*numbers):
    return lispMakeBoolValue(numbers[0].value.exactness)


@primitive("inexact?")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_isInexact(*numbers):
    return lispMakeBoolValue(not numbers[0].value.exactness)


def lispApplyNumberFun(x, y, f):
    realNum, realDenom = f(x.value.real, y.value.real)
    imagNum, imagDenom = f(x.value.imag, y.value.imag)
    return lispMakeNumberValue(realNum, realDenom, imagNum, imagDenom)


@primitive("+")
@allType(LispValueTypes.Number)
def lispPrimitive_add(*numbers):
    def add(x, y):
        lcd = np.lcm(x.denominator, y.denominator)
        if np.isclose(lcd, 1):
            numX = x.getInt()
            numY = y.getInt()
            lcd = int(1)
        else:
            numX = x.getInt() * lcd / x.denominator
            numY = y.getInt() * lcd / y.denominator
        return (numX + numY, lcd)

    result = functools.reduce(lambda a, x: lispApplyNumberFun(a, x, add),
                              numbers,
                              lispMakeNumberValue(0))
    return result


@primitive("*")
@allType(LispValueTypes.Number)
def lispPrimitive_multiply(*numbers):
    def mul(x, y):
        return (x.getInt() * y.getInt(), x.denominator * y.denominator)

    result = functools.reduce(lambda a, x: lispApplyNumberFun(a, x, mul),
                              numbers,
                              lispMakeNumberValue(1))
    return result


@primitive("-")
@allType(LispValueTypes.Number)
@minArgCount(1)
def lispPrimitive_subtract(*numbers):
    def sub(x, y):
        lcd = np.lcm(x.denominator, y.denominator)
        if np.isclose(lcd, 1):
            numX = x.getInt()
            numY = y.getInt()
            lcd = 1
        else:
            numX = x.getInt() * lcd / x.denominator
            numY = y.getInt() * lcd / y.denominator
        return (numX - numY, lcd)

    if (len(numbers) == 1):
        val = lispMakeNumberValue(numbers[0].value.real.numerator, numbers[0].value.real.denominator,
                                  numbers[0].value.imag.numerator, numbers[0].value.imag.denominator)
        val.value.real.sign = -1 * val.value.real.sign
        val.value.imag.sign = -1 * val.value.imag.sign
        return val

    result = functools.reduce(lambda a, x: lispApplyNumberFun(a, x, sub),
                              numbers[1:],
                              numbers[0])
    return result


@primitive("/")
@primitivePrerequesite(lispPrimitive_isReal, "real")
@minArgCount(1)
def lispPrimitive_divide(*numbers):
    @primitivePrerequesite(lispPrimitive_isInteger, "integer")
    def makeRatio(n):
        val = lispMakeNumberValue(1, n.value.real.numerator, 0, 1)
        val.value.real.sign = -1 * val.value.real.sign
        return val

    if (len(numbers) == 1):
        return makeRatio(numbers[0])
    denominator = lispPrimitive_multiply(*numbers[1:]).value
    val = lispMakeNumberValue(numbers[0].value.real.numerator, denominator.real.numerator, 0, 1)
    val.value.real.sign = -1 if numbers[0].value.real.sign != denominator.real.sign else 1
    return val


def lispPrimitive_binary(fn, fnName, *numbers):
    if ((not np.isclose(numbers[0].value.imag.numerator, 0.0))
            or (not np.isclose(numbers[1].value.imag.numerator, 0.0))):
        print("[LispEvalError] Expecting real arguments for '%s'" % fnName)
        return LispEvalContext([], LispValueVoid())

    retVal = fn(numbers[0].value.real.getFloat(), numbers[1].value.real.getFloat())
    return LispValue(retVal, LispValueTypes.Boolean)


@primitive("<")
@allType(LispValueTypes.Number)
@exactArgCount(2)
def lispPrimitive_smaller(*numbers):
    return lispPrimitive_binary(lambda x, y: x < y, "<", *numbers)


@primitive("<=")
@allType(LispValueTypes.Number)
@exactArgCount(2)
def lispPrimitive_smallerEqual(*numbers):
    return lispPrimitive_binary(lambda x, y: x <= y, "<=", *numbers)


@primitive(">")
@allType(LispValueTypes.Number)
@exactArgCount(2)
def lispPrimitive_greater(*numbers):
    return lispPrimitive_binary(lambda x, y: x > y, ">", *numbers)


@primitive(">=")
@allType(LispValueTypes.Number)
@exactArgCount(2)
def lispPrimitive_greaterEqual(*numbers):
    return lispPrimitive_binary(lambda x, y: x >= y, ">=", *numbers)


@primitive("zero?")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_isZero(*numbers):
    return lispMakeBoolValue(np.isclose(numbers[0].value.real.numerator, 0)
                             and np.isclose(numbers[0].value.imag.numerator, 0))


@primitive("positive?")
@primitivePrerequesite(lispPrimitive_isReal, "real")
@exactArgCount(1)
def lispPrimitive_isPositive(*numbers):
    return lispMakeBoolValue(numbers[0].value.real.getFloat() > 0)


@primitive("negative?")
@primitivePrerequesite(lispPrimitive_isReal, "real")
@exactArgCount(1)
def lispPrimitive_isNegative(*numbers):
    return lispMakeBoolValue(numbers[0].value.real.getFloat() < 0)


@primitive("odd?")
@primitivePrerequesite(lispPrimitive_isInexact, "integer")
@exactArgCount(1)
def lispPrimitive_isOdd(*numbers):
    return lispMakeBoolValue(np.mod(numbers[0].value.real.numerator, 2) == 1)


@primitive("even?")
@primitivePrerequesite(lispPrimitive_isInexact, "integer")
@exactArgCount(1)
def lispPrimitive_isEven(*numbers):
    return lispMakeBoolValue(np.mod(numbers[0].value.real.numerator, 2) == 0)


def lispFoldlValues(*values, fn, init, fnName):
    acc = init
    for i in range(len(values)):
        if fn(acc, values[i]):
            acc = values[i]
    return acc


@primitive("max")
@primitivePrerequesite(lispPrimitive_isReal, "real")
@minArgCount(1)
def lispPrimitive_max(*numbers):
    best = numbers[0]
    for i in range(1, len(numbers)):
        if numbers[i].value.real.getFloat() > best.value.real.getFloat():
            best = numbers[i]
    return best


@primitive("min")
@primitivePrerequesite(lispPrimitive_isReal, "real")
@minArgCount(1)
def lispPrimitive_min(*numbers):
    best = numbers[0]
    for i in range(1, len(numbers)):
        if numbers[i].value.real.getFloat() < best.value.real.getFloat():
            best = numbers[i]
    return best


@primitive("abs")
@primitivePrerequesite(lispPrimitive_isReal, "real")
@exactArgCount(1)
def lispPrimitive_abs(*numbers):
    return lispMakeNumberValue(numbers[0].value.real.numerator, numbers[0].value.real.denominator,
                               numbers[0].value.imag.numerator, numbers[0].value.imag.denominator)


@primitive("quotient")
@primitivePrerequesite(lispPrimitive_isInteger, "integer")
@exactArgCount(2)
def lispPrimitive_quotient(*numbers):
    val = int(numbers[0].value.real.getInt() / numbers[1].value.real.getInt())
    return lispMakeNumberValue(val, 1, 0, 1)


@primitive("remainder")
@primitivePrerequesite(lispPrimitive_isReal, "real")
@exactArgCount(2)
def lispPrimitive_remainder(*numbers):
    x = numbers[0].value.real.getInt()
    y = numbers[1].value.real.getInt()
    val = int(np.round((x / y - int(x / y)) * y))
    return lispMakeNumberValue(val, 1, 0, 1)


@primitive("modulo")
@primitivePrerequesite(lispPrimitive_isInteger, "integer")
@exactArgCount(2)
def lispPrimitive_modulo(*numbers):
    y = numbers[1].value.real.getInt()
    rem = lispPrimitive_remainder(*numbers).value.real.getInt()
    val = rem + y if (y * rem) < 0 else rem
    return lispMakeNumberValue(val, 1, 0, 1)


@primitive("gcd")
@primitivePrerequesite(lispPrimitive_isReal, "real")
def lispPrimitive_gcd(*numbers):
    if len(numbers) == 0:
        return lispMakeNumberValue(0, 1, 0, 1)

    gcd = np.gcd.reduce(list(map(lambda n: int(n.value.real.getInt()), numbers)))
    return lispMakeNumberValue(gcd, 1, 0, 1)


@primitive("lcm")
@primitivePrerequesite(lispPrimitive_isReal, "real")
def lispPrimitive_lcm(*numbers):
    if len(numbers) == 0:
        return lispMakeNumberValue(1, 1, 0, 1)

    lcm = np.lcm.reduce(list(map(lambda n: int(n.value.real.getInt()), numbers)))
    return lispMakeNumberValue(lcm, 1, 0, 1)


@primitive("numerator")
@primitivePrerequesite(lispPrimitive_isReal, "real")
@exactArgCount(1)
def lispPrimitive_numerator(*numbers):
    return lispMakeNumberValue(numbers[0].value.real.getInt(), 1, 0, 1)


@primitive("denominator")
@primitivePrerequesite(lispPrimitive_isReal, "real")
@exactArgCount(1)
def lispPrimitive_denominator(*numbers):
    return lispMakeNumberValue(numbers[0].value.real.denominator, 1, 0, 1)


@primitive("floor")
@primitivePrerequesite(lispPrimitive_isReal, "real")
@exactArgCount(1)
def lispPrimitive_floor(*numbers):
    return lispMakeNumberValue(np.floor(numbers[0].value.real.getFloat()))


@primitive("ceiling")
@primitivePrerequesite(lispPrimitive_isReal, "real")
@exactArgCount(1)
def lispPrimitive_ceiling(*numbers):
    return lispMakeNumberValue(np.ceil(numbers[0].value.real.getFloat()))


@primitive("truncate")
@primitivePrerequesite(lispPrimitive_isReal, "real")
@exactArgCount(1)
def lispPrimitive_truncate(*numbers):
    x = numbers[0].value.real.getFloat()
    return lispMakeNumberValue(int(x))


@primitive("round")
@primitivePrerequesite(lispPrimitive_isReal, "real")
@exactArgCount(1)
def lispPrimitive_round(*numbers):
    return lispMakeNumberValue(np.round(numbers[0].value.real.getFloat()))


@primitive("exp")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_exp(*numbers):
    z = np.exp(numbers[0].value.getComplex())
    return lispMakeNumberValue(z.real, 1, z.imag, 1)


@primitive("log")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_log(*numbers):
    z = np.log(numbers[0].value.getComplex())
    return lispMakeNumberValue(z.real, 1, z.imag, 1)


@primitive("sin")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_sin(*numbers):
    z = np.sin(numbers[0].value.getComplex())
    return lispMakeNumberValue(z.real, 1, z.imag, 1)


@primitive("cos")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_cos(*numbers):
    z = np.cos(numbers[0].value.getComplex())
    return lispMakeNumberValue(z.real, 1, z.imag, 1)


@primitive("tan")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_tan(*numbers):
    z = np.tan(numbers[0].value.getComplex())
    return lispMakeNumberValue(z.real, 1, z.imag, 1)


@primitive("asin")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_asin(*numbers):
    z = np.arcsin(numbers[0].value.getComplex())
    return lispMakeNumberValue(z.real, 1, z.imag, 1)


@primitive("acos")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_acos(*numbers):
    z = np.arccos(numbers[0].value.getComplex())
    return lispMakeNumberValue(z.real, 1, z.imag, 1)


@primitive("atan")
@allType(LispValueTypes.Number)
def lispPrimitive_atan(*numbers):
    argcount = len(numbers) == 1
    if argcount == 1:
        z = np.arctan(numbers[0].value.getComplex())
        return lispMakeNumberValue(z.real, 1, z.imag, 1)
    elif argcount == 2:
        x = np.arctan2(numbers[0].value.real.getFloat(), numbers[1].value.real.getFloat())
        return lispMakeNumberValue(x.real, 1, 0, 1)
    else:
        print("[LispEvalError] invalid arg count for atan. Expecting 1 or 2, got %d" % argcount)
        return LispValueVoid()


@primitive("sqrt")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_sqrt(*numbers):
    z = np.sqrt(numbers[0].value.getComplex())
    return lispMakeNumberValue(z.real, 1, z.imag, 1)


@primitive("expt")
@allType(LispValueTypes.Number)
@exactArgCount(2)
def lispPrimitive_expt(*numbers):
    z = np.power(numbers[0].value.getComplex(), numbers[1].value.getComplex())
    return lispMakeNumberValue(z.real, 1, z.imag, 1)


@primitive("make-rectangular")
@primitivePrerequesite(lispPrimitive_isReal, "real")
@exactArgCount(2)
def lispPrimitive_expt(*numbers):
    return lispMakeNumberValue(numbers[0].value.real.getFloat(), 1, numbers[1].value.real.getFloat(), 1)


@primitive("make-polar")
@primitivePrerequesite(lispPrimitive_isReal, "real")
@exactArgCount(2)
def lispPrimitive_expt(*numbers):
    r = numbers[0].value.real.getFloat()
    theta = numbers[1].value.real.getFloat()
    a = r * np.cos(theta)
    b = r * np.sin(theta)
    return lispMakeNumberValue(a, 1, b, 1)


@primitive("real-part")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_complexReal(*numbers):
    return lispMakeNumberValue(numbers[0].value.real.getFloat(), 1, 0, 1)


@primitive("imag-part")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_complexImag(*numbers):
    return lispMakeNumberValue(numbers[0].value.imag.getFloat(), 1, 0, 1)


@primitive("magnitude")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_complexMagnitude(*numbers):
    real = numbers[0].value.real.getFloat()
    imag = numbers[0].value.imag.getFloat()
    mag = np.sqrt(real * real + imag * imag)
    return lispMakeNumberValue(mag, 1, 0, 1)


@primitive("angle")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_complexAngle(*numbers):
    real = numbers[0].value.real.getFloat()
    imag = numbers[0].value.imag.getFloat()
    angle = np.arctan2(imag, real)
    return lispMakeNumberValue(angle, 1, 0, 1)


@primitive("exact->inexact")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_exactInexact(*numbers):
    if not numbers[0].value.exactness:
        return numbers[0]
    else:
        return lispMakeNumberValue(numbers[0].value.real.getFloat(), 1, numbers[0].value.imag.getFloat(), 1)


@primitive("inexact->exact")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_exactInexact(*numbers):
    if numbers[0].value.exactness:
        return numbers[0]
    else:
        def conv(n):
            f = n.getFloat()
            base = int(1e10)
            big = int(f * base)
            gcd = np.gcd(big, base)
            return (big / gcd, base / gcd)

        real_num, real_denom = conv(numbers[0].value.real)
        imag_num, imag_denom = conv(numbers[0].value.imag)
        return lispMakeNumberValue(real_num, real_denom, imag_num, imag_denom)


@primitive("number->string")
@allType(LispValueTypes.Number)
@exactArgCount(1)
def lispPrimitive_numToStr(*numbers):
    def printFrac(n):
        real_num = n.getInt()
        real_denom = n.denominator
        if np.isclose(real_denom, 1, atol=0.0001):
            return "%d" % real_num
        else:
            return "%d/%d" % (real_num, real_denom)

    if numbers[0].value.exactness:
        str = printFrac(numbers[0].value.real)
        if not np.isclose(numbers[0].value.imag.getInt(), 0, atol=0.0001):
            str += "+" + printFrac(numbers[0].value.imag) + "i"
        return lispMakeString(str)
    else:
        str = "%s" % numbers[0].value.real.getFloat()
        imag = numbers[0].value.imag.getFloat()
        if not np.isclose(imag, 0, atol=0.0001):
            str += "+%si" % imag
        return lispMakeString(str)


@primitive("string->number")
@allType(LispValueTypes.String)
@exactArgCount(1)
def lispPrimitive_strToNum(*numbers):
    return LispValue(lexNumber(numbers[0].value).extra, LispValueTypes.Number)


##-----------------------------------------------------------------------------
## equality procedures

@primitive("=")
@allType(LispValueTypes.Number)
def lispPrimitive_equalNum(*numbers):
    if len(numbers) == 0:
        return lispMakeBoolValue(True)

    for i in range(1, len(numbers)):
        if not numbers[i - 1].value.equals(numbers[i].value):
            return lispMakeBoolValue(False)
    return lispMakeBoolValue(True)


@allType(LispValueTypes.Char)
def lispPrimitive_equalChr(*args):
    for i in range(len(args) - 1):
        if args[i].value != args[i + 1].value:
            return LispValueBool(False)
    return LispValueBool(True)


@minArgCount(4)
def lispPrimitive_equalStr(strType=LispValueTypes.String, getStr=lambda s: s.value, *args):
    if not all(c.valueType == strType for c in args):
        print("[LispEvalError] expecting only character arguments for 'string=?'... got: %s" % str(args))
        return LispEvalContext([], LispValueVoid())

    if len(args) == 0:
        return LispValueBool(True)

    l0 = len(getStr(args[0]))
    if not all(len(getStr(args[i])) == l0 for i in range(1, len(args))):
        return LispValueBool(False)

    for i in range(l0):
        c0 = getStr(args[0])[i]
        if not all(getStr(args[s])[i] == c0 for s in range(1, len(args))):
            return LispValueBool(False)
    return LispValueBool(True)


@primitive("null?")
@exactArgCount(1)
def lispPrimitive_null(*args):
    return LispValueBool(args[0].valueType == LispValueTypes.Pair
                         and args[0].value.head == []
                         and args[0].value.tail == False)


@primitive("eqv?")
@exactArgCount(2)
def lispPrimitive_eqv(*args):
    if args[0].valueType != args[1].valueType:
        return LispValueBool(False)
    elif args[0].valueType == LispValueTypes.Boolean:
        return args[0].value == args[1].value
    elif args[0].valueType == LispValueTypes.Char:
        return lispPrimitive_equalChr(*args)
    elif args[0].valueType == LispValueTypes.Number:
        return lispPrimitive_equalNum(*args)
    elif args[0].valueType == LispValueTypes.String:
        return lispPrimitive_equalStr(LispValueTypes.String, lambda s: s.value, *args)
    elif args[0].valueType == LispValueTypes.Symbol:
        return lispPrimitive_equalStr(LispValueTypes.Symbol, lambda s: s.value.text, *args)
    elif args[0].valueType == LispValueTypes.Pair:
        if (lispPrimitive_null(args[0]).value
                and lispPrimitive_null(args[1]).value):
            return LispValueBool(True)

    return args[0].value == args[1].value


@primitive("equal?")
@exactArgCount(2)
def lispPrimitive_equal(*args):
    def equal_rec(x, y):
        # print("test: %s, %s" % (x,y))
        if type(x) != type(y):
            return LispValueBool(False)

        if isinstance(x, LispAST_Quotation):
            return equal_rec(x.datum, y.datum)

        if isinstance(x, LispAST_List):
            if len(x.head) != len(y.head):
                return LispValueBool(False)
            for i in range(len(x.head)):
                if not equal_rec(x.head[i], y.head[i]):
                    return LispValueBool(False)
            if x.tail != y.tail or (x.tail and not equal_rec(x.tail, y.tail)):
                return LispValueBool(False)
            else:
                return LispValueBool(True)
        elif isinstance(x, LispAST_Vector):
            if len(x.content) != len(y.content):
                return LispValueBool(False)
            for i in range(len(x.content)):
                if not equal_rec(x.content[i], y.content[i]):
                    return LispValueBool(False)
            return LispValueBool(True)
        elif isinstance(x, LispAST_Abbreviation):
            return equal_rec(x.datum, y.datum)
        elif isinstance(x, LispAST_Symbol):
            return lispPrimitive_equalStr(LispValueTypes.Symbol,
                                          lambda s: s.value.text,
                                          LispValue(x, LispValueTypes.Symbol),
                                          LispValue(y, LispValueTypes.Symbol))
        elif isinstance(x, LispAST_token):
            if x.tokenType == LispTokenTypes.Number:
                return lispPrimitive_equalNum(LispValue(x.extra, LispValueTypes.Number),
                                              LispValue(y.extra, LispValueTypes.Number))
            elif x.tokenType == LispTokenTypes.Character:
                return lispPrimitive_equalChr(LispValue(x.extra, LispValueTypes.Char),
                                              LispValue(y.extra, LispValueTypes.Char))
            elif x.tokenType == LispTokenTypes.String:
                return lispPrimitive_equalStr(LispValueTypes.String,
                                              lambda s: s.value,
                                              LispValue(x.extra, LispValueTypes.String),
                                              LispValue(y.extra, LispValueTypes.String))
            elif x.tokenType == LispTokenTypes.Boolean:
                return x.extra == y.extra

            else:
                raise Exception("Unexpected token... of type : %s" % str(list(map(lambda x: type(x).__name__, args))))
        else:
            raise Exception("Unexpected datum... of type: %s" % str(list(map(lambda x: type(x).__name__, args))))

    return equal_rec(args[0].value, args[1].value)


##-----------------------------------------------------------------------------
## Eval!

def lispPrimevalEnv():
    primevalEnv = dict()
    for p in primitive.env:
        id = p[0]
        prim = p[1]
        primevalEnv[id] = lispMakePrimitive(id, prim)

    primevalEnv['char=?'] = LispValue(LispAST_Primitive('char=?', lispPrimitive_equalChr),
                                      LispValueTypes.Primitive)
    primevalEnv['string=?'] = LispValue(LispAST_Primitive('string=?',
                                                          lambda *args: lispPrimitive_equalStr(LispValueTypes.String,
                                                                                               lambda s: s.value,
                                                                                               *args)),
                                        LispValueTypes.Primitive)
    return primevalEnv


def lispEvalAST(ast):
    return ast.eval(lispPrimevalEnv()).value


def lispEval(str):
    tokens = parseTokens(str)
    if not tokens:
        print("lexical error in input, cannot evaluate...")
        return
    program = parseProgram(tokens)
    if not program:
        print("syntaxic error in input, cannot evaluate...")
        return
    env = lispPrimevalEnv()
    result = LispValueVoid()
    for expr in program.result[0]:
        result = expr.eval(env)
        env = result.env
    return result.value


###############################################################################
## Unit tests

class TestLispLex(unittest.TestCase):
    def testComment(self):
        self.assertTrue(lexComment(";asdfasdf; asdsdaf").result == ";asdfasdf; asdsdaf")
        self.assertFalse(lexComment(" ;asdfasdf; asdsdaf"))
        self.assertFalse(lexComment("asdfsdf"))

    def testWhitespace(self):
        self.assertTrue(lexWhitespace("   \t  \n safadf").result == "   \t  \n ")
        self.assertTrue(lexWhitespace("\t  \n safadf").result == "\t  \n ")
        self.assertTrue(lexWhitespace("\n  \n safadf").result == "\n  \n ")
        self.assertTrue(lexWhitespace("\r  \n safadf").result == "\r  \n ")
        self.assertFalse(lexWhitespace("a  \n safadf"))

    def testDelimiter(self):
        self.assertTrue(lexDelimiter("|sdafsa|sdaf").result == "|")
        self.assertTrue(lexDelimiter("; comment").result == ";")
        self.assertTrue(lexDelimiter("   allo").result == "   ")
        self.assertTrue(lexDelimiter("\n(allo)").result == "\n")
        self.assertFalse(lexDelimiter("@llo)"))

    def testAtmosphere(self):
        self.assertTrue(lexAtmosphere("   allo").result == "   ")
        self.assertTrue(lexAtmosphere(";dsfffdfasf\n   allo").result == ";dsfffdfasf\n")
        self.assertTrue(lexAtmosphere("\n    \t;  dsfffdfasf\n   allo").result == "\n    \t")

    def testInterTokenSpace(self):
        self.assertTrue(lexInterTokenSpace(";dsfffdfasf\n   allo").result == ";dsfffdfasf\n   ")
        self.assertTrue(
            lexInterTokenSpace(";dsfffdfasf\n   \t\r  ;asdfsdaf\nallo").result == ";dsfffdfasf\n   \t\r  ;asdfsdaf\n")
        self.assertTrue(lexInterTokenSpace("\r;dsfffdfasfa\nallo   \tf\nallo").result == "\r;dsfffdfasfa\n")
        self.assertFalse(lexInterTokenSpace("#f\r;dsfffdfasfa\nallo   \tf\nallo").result == "\r;dsfffdfasfa\n")

    def testLetter(self):
        self.assertTrue(lexLetter("a"))
        self.assertTrue(lexLetter("z"))
        self.assertTrue(lexLetter("A"))
        self.assertTrue(lexLetter("Z"))
        self.assertFalse(lexLetter("("))
        self.assertFalse(lexLetter("7"))

    def testSpecialInitial(self):
        self.assertTrue(lexSpecialInitial("!"))
        self.assertTrue(lexSpecialInitial("*"))
        self.assertTrue(lexSpecialInitial("?"))
        self.assertFalse(lexSpecialInitial("a"))

    def testDigit(self):
        self.assertTrue(lexDigit("9"))
        self.assertTrue(lexDigit("1"))
        self.assertTrue(lexDigit("0"))
        self.assertFalse(lexDigit("a"))
        self.assertTrue(lexDigit("a", 16))
        self.assertTrue(lexDigit("D", 16))
        self.assertFalse(lexDigit("9", 8))

    def testSpecialSubsequent(self):
        self.assertTrue(lexSpecialSubsequent("@"))
        self.assertTrue(lexSpecialSubsequent("+"))
        self.assertTrue(lexSpecialSubsequent("-"))
        self.assertFalse(lexSpecialSubsequent("&"))
        self.assertFalse(lexSpecialSubsequent("a"))
        self.assertFalse(lexSpecialSubsequent("0"))

    def testPeculiarIdentifier(self):
        self.assertTrue(lexPeculiarIdentifier("+"))
        self.assertTrue(lexPeculiarIdentifier("-"))
        self.assertFalse(lexPeculiarIdentifier("@"))

    def testInitial(self):
        self.assertTrue(lexInitial("a"))
        self.assertTrue(lexInitial("*"))
        self.assertFalse(lexInitial("@"))

    def testSubsequent(self):
        self.assertTrue(lexSubsequent("a"))
        self.assertTrue(lexSubsequent("@"))
        self.assertTrue(lexSubsequent("5"))
        self.assertTrue(lexSubsequent("+"))
        self.assertFalse(lexSubsequent("\r"))

    def testIdentifier(self):
        self.assertTrue(lexIdentifier("allo*@556"))
        self.assertTrue(lexIdentifier("test!"))
        self.assertTrue(lexIdentifier("$test?"))
        self.assertTrue(lexIdentifier("<test>"))
        self.assertFalse(lexIdentifier("@allo"))
        self.assertFalse(lexIdentifier("#allo"))

    def testExpressionKeyword(self):
        self.assertTrue(lexExpressionKeyword("quote"))
        self.assertTrue(lexExpressionKeyword("lambda"))
        self.assertTrue(lexExpressionKeyword("if"))
        self.assertTrue(lexExpressionKeyword("cond"))
        self.assertFalse(lexExpressionKeyword("allo"))
        self.assertFalse(lexExpressionKeyword("quota"))

    def testSynacticKeyword(self):
        self.assertTrue(lexSynacticKeyword("else"))
        self.assertTrue(lexSynacticKeyword("define"))
        self.assertTrue(lexSynacticKeyword("unquote"))
        self.assertFalse(lexSynacticKeyword("1234"))
        self.assertFalse(lexSynacticKeyword("allo"))

    def testBoolean(self):
        self.assertTrue(lexBoolean("#f"))
        self.assertTrue(lexBoolean("#t"))
        self.assertFalse(lexBoolean("true"))
        self.assertFalse(lexBoolean("false"))

    def testAnyCharacter(self):
        self.assertTrue(lexAnyCharacter("a"))
        self.assertTrue(lexAnyCharacter("#"))
        self.assertTrue(lexAnyCharacter("?"))
        self.assertTrue(lexAnyCharacter("("))

    def testCharacterName(self):
        self.assertTrue(lexCharacterName("space"))
        self.assertTrue(lexCharacterName("newline"))
        self.assertFalse(lexCharacterName("newlin"))
        self.assertFalse(lexCharacterName("alllo"))

    def testCharacter(self):
        self.assertTrue(lexCharacter("#\\a"))
        self.assertTrue(lexCharacter("#\\("))
        self.assertTrue(lexCharacter("#\\\\"))
        self.assertTrue(lexCharacter("#\\#"))
        self.assertFalse(lexCharacter("##"))

    def testString(self):
        self.assertTrue(lexString("\"asdflkj   sdlkfjf\""))
        self.assertTrue(lexString("\"asdflkj \\\"hello\\\"   sdlkfjf\""))
        self.assertTrue(lexString("\"asdflkj c:\\\\users\\\\john\""))
        self.assertFalse(lexString("allo"))
        self.assertFalse(lexString("\"allo"))
        self.assertFalse(lexString("allo\""))
        self.assertFalse(lexString("1234"))

    def testCompose(self):
        self.assertTrue(
            lexCompose(";asd\nallo  ifblabla", [lexComment, lexIdentifier, lexAtmosphere, lexExpressionKeyword]))

    def testSign(self):
        self.assertTrue(lexSign("+"))
        self.assertTrue(lexSign("-"))
        self.assertTrue(lexSign(""))

    def testUInteger(self):
        self.assertTrue(lexUInteger("12345", 10).result == "12345")
        self.assertTrue(lexUInteger("0989845", 10).result == "0989845")
        self.assertTrue(lexUInteger("09898453297237953795923", 10).result == "09898453297237953795923")
        self.assertTrue(lexUInteger("09898453297237953795923.111", 10).result == "09898453297237953795923")
        self.assertFalse(lexUInteger(".09898453297237953795923", 10))
        self.assertTrue(lexUInteger("01110101101", 2).result == "01110101101")
        self.assertFalse(lexUInteger("201110101101", 2))
        self.assertTrue(lexUInteger("156765137136734", 8).result == "156765137136734")
        self.assertTrue(lexUInteger("f123ABCDEF13", 16).result == "f123ABCDEF13")

    def testRadix(self):
        self.assertTrue(lexRadix("#b", 2, LispAST_Number()))
        self.assertTrue(lexRadix("#o", 8, LispAST_Number()))
        self.assertTrue(lexRadix("#d", 10, LispAST_Number()))
        self.assertTrue(lexRadix("#x", 16, LispAST_Number()))
        self.assertFalse(lexRadix("#x", 2, LispAST_Number()))
        self.assertFalse(lexRadix("#o", 16, LispAST_Number()))

    def testExponentMarker(self):
        self.assertTrue(lexExponentMarker("e"))
        self.assertTrue(lexExponentMarker("s"))
        self.assertTrue(lexExponentMarker("f"))
        self.assertTrue(lexExponentMarker("d"))
        self.assertTrue(lexExponentMarker("l"))
        self.assertFalse(lexExponentMarker("b"))

    def testExactness(self):
        self.assertTrue(lexExactness("#i", LispAST_Number()))
        self.assertTrue(lexExactness("#e", LispAST_Number()))

    def testNumberPrefix(self):
        self.assertTrue(lexNumberPrefix("#x#e", 16, LispAST_Number()).result == "#x#e")
        self.assertTrue(lexNumberPrefix("#b#i", 2, LispAST_Number()))
        self.assertTrue(lexNumberPrefix("#i#o", 8, LispAST_Number()))
        self.assertTrue(lexNumberPrefix("#i#d", 10, LispAST_Number()))
        self.assertTrue(lexNumberPrefix("#i", 10, LispAST_Number()))
        self.assertTrue(lexNumberPrefix("", 10, LispAST_Number()))

    def testNumberSuffix(self):
        self.assertTrue(lexNumberSuffix("e+12345allo").result == "e+12345")
        self.assertTrue(lexNumberSuffix("e-12345"))
        self.assertTrue(lexNumberSuffix("e12345"))
        self.assertTrue(lexNumberSuffix("s12345"))
        self.assertTrue(lexNumberSuffix("d+12345"))
        self.assertTrue(lexNumberSuffix("l+12345"))

    def testDecimal(self):
        self.assertFalse(lexDecimal("12345"))
        self.assertTrue(lexDecimal("12345e+10"))
        self.assertTrue(lexDecimal("12345e-0"))
        self.assertTrue(lexDecimal(".12345e-0"))
        self.assertFalse(lexDecimal(".e-0"))
        self.assertTrue(lexDecimal("12345.12345e10"))
        self.assertTrue(lexDecimal("12345.12345"))
        self.assertTrue(lexDecimal("12345###.###e10"))

    def testURealNumber(self):
        self.assertTrue(lexURealNumber("12345", 10))
        self.assertTrue(lexURealNumber("12345/12345", 10))
        self.assertTrue(lexURealNumber("123.456e-10", 10))
        self.assertTrue(lexURealNumber("11010101", 2))
        self.assertTrue(lexURealNumber("1214124677776", 8))
        self.assertTrue(lexURealNumber("a7d580fff/fcc445", 16))
        self.assertFalse(lexURealNumber("a7d580fff/fcc445", 8))
        self.assertTrue(lexURealNumber("123", 2).result != "123")

    def testRealNumber(self):
        self.assertTrue(lexRealNumber("+123.456e-10", 10).result == "+123.456e-10")
        self.assertTrue(lexRealNumber("-1234567", 8).result == "-1234567")
        self.assertTrue(lexRealNumber("+123456789abcdef", 16).result == "+123456789abcdef")
        self.assertTrue(lexRealNumber("+101010101111", 2).result == "+101010101111")
        self.assertTrue(lexRealNumber("+101210101111", 2).result != "+101210101111")

    def testNumberComplex(self):
        self.assertTrue(lexNumberComplex("123@456.789", 10, LispAST_Number()).result == "123@456.789")
        self.assertTrue(lexNumberComplex("-123.456+789.10i", 10, LispAST_Number()).result == "-123.456+789.10i")
        self.assertTrue(lexNumberComplex("-123.456-789.10e10i", 10, LispAST_Number()).result == "-123.456-789.10e10i")
        self.assertTrue(lexNumberComplex("-123.456e10+i", 10, LispAST_Number()).result == "-123.456e10+i")
        self.assertTrue(lexNumberComplex("-123.456e10-i", 10, LispAST_Number()).result == "-123.456e10-i")
        self.assertTrue(lexNumberComplex("+i", 10, LispAST_Number()).result == "+i")
        self.assertTrue(lexNumberComplex("+123.456e-10i", 10, LispAST_Number()).result == "+123.456e-10i")
        self.assertTrue(lexNumberComplex("-123.456e-10i", 10, LispAST_Number()).result == "-123.456e-10i")
        self.assertTrue(lexNumberComplex("10011-101100i", 2, LispAST_Number()).result == "10011-101100i")
        self.assertTrue(lexNumberComplex("1234567+1234567i", 8, LispAST_Number()).result == "1234567+1234567i")
        self.assertTrue(lexNumberComplex("-123456789abcdefi", 16, LispAST_Number()).result == "-123456789abcdefi")

    def testNumberBase(self):
        self.assertTrue(
            lexNumberBase("#d1234.5678e-9+543.21i", 10, LispAST_Number()).result == "#d1234.5678e-9+543.21i")
        self.assertTrue(lexNumberBase("#b10110", 2, LispAST_Number()).result == "#b10110")
        self.assertTrue(lexNumberBase("#o1234567-i", 8, LispAST_Number()).result == "#o1234567-i")
        self.assertTrue(lexNumberBase("#xabcdef-abc123i", 16, LispAST_Number()).result == "#xabcdef-abc123i")
        self.assertTrue(
            lexNumberBase("#e#d1234.5678e-9+543.21i", 10, LispAST_Number()).result == "#e#d1234.5678e-9+543.21i")

    def testNumber(self):
        self.assertTrue(lexNumber("#e1234.567e-89-i").result == "#e1234.567e-89-i");
        self.assertTrue(lexNumber("#i1234.567e-89-i").result == "#i1234.567e-89-i");
        self.assertTrue(lexNumber("-12.99e10i").result == "-12.99e10i");
        self.assertTrue(lexNumber("#b101011-011i").result == "#b101011-011i")
        self.assertTrue(lexNumber("#o#e1234/5676+77i").result == "#o#e1234/5676+77i")
        self.assertTrue(lexNumber("#xabcde/123-456abci").result == "#xabcde/123-456abci")
        self.assertTrue(lexNumber("#xabcde").result == "#xabcde")
        self.assertFalse(lexNumber("abcde"))

    def testToken(self):
        self.assertTrue(lexToken("allo"))
        self.assertTrue(lexToken("$hello"))
        self.assertTrue(lexToken("#t"))
        self.assertTrue(lexToken("#e#d123.456e-789/123.56-i"))
        self.assertTrue(lexToken("#\\a"))
        self.assertTrue(lexToken("\"hello \\\"world\\\"!\""))
        self.assertTrue(lexToken("("))
        self.assertTrue(lexToken(")"))
        self.assertTrue(lexToken("#("))
        self.assertTrue(lexToken("'"))
        self.assertTrue(lexToken("`"))
        self.assertTrue(lexToken(","))
        self.assertTrue(lexToken(",@"))
        self.assertTrue(lexToken("."))

    def testParseTokens(self):
        self.assertTrue(len(parseTokens("(allo 1.134e10+i #f #\\a #(allo \"world\"))")) == 10)

    def testParseTokenType(self):
        self.assertTrue(parseTokenType(parseTokens("1.23+5i"), LispTokenTypes.Number, LispAST_token))
        self.assertTrue(parseTokenType(parseTokens("(allo)"), LispTokenTypes.LParen, LispAST_token))
        self.assertTrue(parseTokenType(parseTokens(",@(allo)"), LispTokenTypes.CommaSplice, LispAST_token))

    def testParseSimpleDatum(self):
        self.assertTrue(parseSimpleDatum(parseTokens("allo")).rest == [])
        self.assertTrue(parseSimpleDatum(parseTokens("1.13e-13+i")).rest == [])
        self.assertTrue(parseSimpleDatum(parseTokens("#f")).rest == [])
        self.assertTrue(parseSimpleDatum(parseTokens("\"stringg \\\"str\\\" hello\"")).rest == [])

    def testParseList(self):
        self.assertTrue(parseList(parseTokens("(allo (sdf . asfsadf))")).rest == [])
        self.assertTrue(parseList(parseTokens("(car . cdr)")).rest == [])
        self.assertTrue(parseList(parseTokens("(car 1.13+i #\\a #f . (a b c 12 . ()))")).rest == [])

    def testParseVector(self):
        self.assertTrue(parseVector(parseTokens("#(1 2 3 4)")).rest == [])
        self.assertFalse(parseVector(parseTokens("#(1 2 3 . 4)")))
        self.assertFalse(parseVector(parseTokens("(1 2 3 4)")))

    def testParseCompoundDatum(self):
        self.assertTrue(parseCompoundDatum(parseTokens("'(allo #(1 2 3))")).rest == [])
        self.assertTrue(parseCompoundDatum(parseTokens("'(car . cdr)")).rest == [])
        self.assertTrue(parseCompoundDatum(parseTokens("`(one two)")).rest == [])
        self.assertTrue(parseCompoundDatum(parseTokens(",(one two)")).rest == [])
        self.assertTrue(parseCompoundDatum(parseTokens(",@(one two)")).rest == [])

    def testParseDatum(self):
        self.assertTrue(parseDatum(parseTokens(",@(allo ,(1 2 . nil) #(1 2 3))")).rest == [])
        self.assertFalse(parseDatum(parseTokens(",@(allo ,(1 2 . nil) #(1 2 . 3))")))

    def testParseQuotation(self):
        self.assertTrue(parseQuotation(parseTokens("'(allo 13 . 4)")).rest == [])
        self.assertTrue(parseQuotation(parseTokens("(quote (allo 13 4))")).rest == [])
        self.assertTrue(parseQuotation(parseTokens("(quote `(allo 13 4))")).rest == [])

    def testParseVariable(self):
        self.assertTrue(parseVariable(parseTokens("allo")))
        self.assertTrue(parseVariable(parseTokens("allo?")))
        self.assertTrue(parseVariable(parseTokens("<allo>?")))
        self.assertTrue(parseVariable(parseTokens("<define>?")))
        self.assertTrue(parseVariable(parseTokens("defin?")))
        self.assertTrue(parseVariable(parseTokens("double")))
        self.assertTrue(parseVariable(parseTokens("define?")))
        self.assertTrue(parseVariable(parseTokens("if?")))
        self.assertFalse(parseVariable(parseTokens("quote")))

    def testParseSelfEvaluating(self):
        self.assertTrue(parseSelfEvaluating(parseTokens("#t")))
        self.assertTrue(parseSelfEvaluating(parseTokens("#f")))
        self.assertTrue(parseSelfEvaluating(parseTokens("1.134e-10-123i")))
        self.assertTrue(parseSelfEvaluating(parseTokens("#b1010011")))
        self.assertTrue(parseSelfEvaluating(parseTokens("#xABCDEF")))
        self.assertTrue(parseSelfEvaluating(parseTokens("#\\?")))
        self.assertTrue(parseSelfEvaluating(parseTokens("\"hello \\\"world\\\"\"")))

    def testParseLitteral(self):
        self.assertTrue(parseLitteral(parseTokens("'(hello world)")))
        self.assertTrue(parseLitteral(parseTokens("(quote (hello world))")))
        self.assertTrue(parseLitteral(parseTokens("(quote '(hello world))")))
        self.assertFalse(parseLitteral(parseTokens("(quote '(hello world)")))
        self.assertTrue(parseLitteral(parseTokens("#t")))
        self.assertTrue(parseLitteral(parseTokens("#o1234567")))
        self.assertFalse(parseLitteral(parseTokens("#o12345678")))
        self.assertFalse(parseLitteral(parseTokens("#a")))

    def testParseProcedureCall(self):
        self.assertTrue(parseProcedureCall(parseTokens("(fact! 10)")))
        self.assertTrue(parseProcedureCall(parseTokens("(thunk)")))
        self.assertTrue(parseProcedureCall(parseTokens("(thunk  )")))
        self.assertTrue(parseProcedureCall(parseTokens("(fib 1 2)")))
        self.assertTrue(parseProcedureCall(parseTokens("(f (g x))")))
        self.assertTrue(parseProcedureCall(parseTokens("(print '(1 2 3 4 5))")))
        self.assertTrue(parseProcedureCall(parseTokens("(map (lambda (x) (+ x 1)) '(1 2 3 4 5))")))
        self.assertFalse(parseProcedureCall(parseTokens("(lambda (lambda (x) (+ x 1)) '(1 2 3 4 5))")))
        self.assertFalse(parseProcedureCall(parseTokens("(if #t 1 2)")))
        self.assertFalse(parseProcedureCall(parseTokens("()")))

    def testParseLambdaExpression(self):
        self.assertTrue(parseLambdaExpression(parseTokens("(lambda (x) x)")))
        self.assertTrue(parseLambdaExpression(parseTokens("(lambda (x) (+ x 1))")))
        self.assertTrue(parseLambdaExpression(parseTokens("(lambda (x y z) (+ x y z))")))
        self.assertTrue(parseLambdaExpression(parseTokens("(lambda (x . rest) (foldl + x rest))")))
        self.assertTrue(parseLambdaExpression(parseTokens("(lambda () (print \"hello world\"))")))
        self.assertTrue(parseLambdaExpression(parseTokens("(lambda () (print 'test) (newline) (print 'test2))")))

    def testParseConditional(self):
        self.assertTrue(parseConditional(parseTokens("(if #t 'yes 'no)")))
        self.assertTrue(parseConditional(parseTokens("(if #t 'yes)")))
        self.assertTrue(parseConditional(parseTokens("(if (test) '#(1 2 3) (lambda (x) x))")))
        self.assertFalse(parseConditional(parseTokens("(iff #t 'true 'false)")))
        self.assertFalse(parseConditional(parseTokens("(if #t)")))

    def testParseAssignement(self):
        self.assertTrue(parseAssignement(parseTokens("(set! x 'allo)")))
        self.assertTrue(parseAssignement(parseTokens("(set! ^abc^ (+ 1 2))")))
        self.assertTrue(parseAssignement(parseTokens("(set! t? (if #t 'true 'false))")))
        self.assertFalse(parseAssignement(parseTokens("(set!! x 1)")))
        self.assertFalse(parseAssignement(parseTokens("(set! 'x 1)")))
        self.assertFalse(parseAssignement(parseTokens("(set! (x) 1)")))

    # def testParseDerivedExpression(self):
    #     self.assertTrue(parseDerivedExpression(parseTokens("(cond (#t 'true))")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(cond (abc 'true)((deg) 'true))")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(cond (abc 'true)((deg) 'true) (else #f))")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(cond (#t))")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(cond (#t => (lambda (x) x)))")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(case (fn-call) ((allo) 'allo))")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(case v ((allo) 'allo)) (else (+ 1 2)))")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(and one two three four)")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(and)")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(or one two three four)")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(or)")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(let ((x 1)) x)")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(let ((x 1)(y 2)) (+ x y))")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(let ((x 1)(y 2)) (+ x y))")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(let v ((x 1)(y 2)) (+ x y))")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(let* ((x 1)(y 2)) (+ x y))")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(letrec ((x 1)(y 2)) (+ x y))")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(begin a b c d)")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(do ((x 0 1) (y 'a)) (#t 'yes) (pp 'a))")))
    #     self.assertTrue(parseDerivedExpression(parseTokens("(delay (lambda (x) x))")))
    #     # todo: add quasiquote tests

    # def testParseExpression(self):
    #     self.assertTrue(parseExpression(parseTokens("'(allo)")))
    #     self.assertTrue(parseExpression(parseTokens("(allo)")))
    #     self.assertTrue(parseExpression(parseTokens("(+ 1 2)")))
    #     self.assertTrue(parseExpression(parseTokens("(if #t 'y 'n)")))
    #     self.assertTrue(parseExpression(parseTokens("(let ((x #t)) (if x 'y (no)))")))

    # parseMacroUse(tokens):
    # parseMacroBlock(tokens):
    # parseDefinition(tokens):
    # parseQuasiQuotation(tokens):

    def isEqual(self, n, r, i, eps=0.0001):
        return (np.isclose(n.real.getFloat(), r, atol=eps)
                and np.isclose(n.imag.getFloat(), i, atol=eps))

    def testEval(self):
        val = lispEvalAST(parseExpression(parseTokens("12e3+5i")).result[0])
        self.assertTrue(self.isEqual(val.value, 12000.0, 5.0))

        val2 = lispEvalAST(parseExpression(parseTokens("#b101")).result[0])
        self.assertTrue(self.isEqual(val2.value, 5.0, 0.0))

        valFalse = lispEvalAST(parseExpression(parseTokens("#f")).result[0])
        self.assertTrue(valFalse.value == False)

        valTrue = lispEvalAST(parseExpression(parseTokens("#t")).result[0])
        self.assertTrue(valTrue.value == True)

        valCharZ = lispEvalAST(parseExpression(parseTokens("#\\Z")).result[0])
        self.assertTrue(valCharZ.value == "Z")

        valStr = lispEvalAST(parseExpression(parseTokens("\"hello World\"")).result[0])
        self.assertTrue(valStr.value == "hello World")

        valLam = lispEvalAST(parseExpression(parseTokens("(lambda (x) x)")).result[0])
        self.assertTrue(valLam.valueType == LispValueTypes.Procedure)

        valLamCall1 = lispEvalAST(parseExpression(parseTokens("((lambda (x) x) 1)")).result[0])
        self.assertTrue(self.isEqual(valLamCall1.value, 1, 0))

        valLamCall2 = lispEvalAST(parseExpression(parseTokens("((lambda (x y) y) 1 2)")).result[0])
        self.assertTrue(self.isEqual(valLamCall2.value, 2, 0))

        valLamCall1r = lispEvalAST(parseExpression(parseTokens("((lambda (x . r) r) 1 2 3)")).result[0])
        self.assertTrue(len(valLamCall1r.value.head) == 2)

        valLamCalln = lispEvalAST(parseExpression(parseTokens("((lambda n n) 1 2 3)")).result[0])
        self.assertTrue(len(valLamCalln.value.head) == 3)

        valLamCallPrim = lispEvalAST(
            parseExpression(parseTokens("((lambda (x y z) (- x y z)) 10 2 (- 4.4-3i))")).result[0])
        self.assertTrue(self.isEqual(valLamCallPrim.value, 12.4, 3.0))

        valLamCallDef = lispEvalAST(
            parseExpression(parseTokens("((lambda (x) (define (double x) (+ x x)) (double x)) #xFF)")).result[0])
        self.assertTrue(self.isEqual(valLamCallDef.value, 510, 0))

        valQuote1 = lispEvalAST(parseExpression(parseTokens("'(a b c)")).result[0])
        self.assertTrue(valQuote1.valueType == LispValueTypes.Pair)

        valQuote2 = lispEvalAST(parseExpression(parseTokens("''(a b c)")).result[0])
        self.assertTrue(valQuote2.valueType == LispValueTypes.Pair)

        valQuote3 = lispEvalAST(parseExpression(parseTokens("'#(a b c)")).result[0])
        self.assertTrue(valQuote3.valueType == LispValueTypes.Vector)

        valIf = lispEvalAST(parseExpression(parseTokens("(if #f 'yes 'no)")).result[0])
        self.assertTrue(valIf.value.text == "no")

        valIf2 = lispEvalAST(parseExpression(parseTokens("(if #t 'yes 'no)")).result[0])
        self.assertTrue(valIf2.value.text == "yes")

        valIf3 = lispEvalAST(parseExpression(parseTokens("(if 'no 'yes 'no)")).result[0])
        self.assertTrue(valIf3.value.text == "yes")

        valIf4 = lispEvalAST(parseExpression(parseTokens("(if ((lambda (x) #t) 3) 'yes 'no)")).result[0])
        self.assertTrue(valIf4.value.text == "yes")

        valCmp1 = lispEvalAST(parseExpression(parseTokens("(if (< 1 2) 'yes 'no)")).result[0])
        self.assertTrue(valCmp1.value.text == "yes")

        valCmp2 = lispEvalAST(parseExpression(parseTokens("(if (<= 2.22 2.22) 'yes 'no)")).result[0])
        self.assertTrue(valCmp2.value.text == "yes")

        valCmp3 = lispEvalAST(parseExpression(parseTokens("(if (>= #xFF #xFF) 'yes 'no)")).result[0])
        self.assertTrue(valCmp3.value.text == "yes")

        valCmp4 = lispEvalAST(parseExpression(parseTokens("(if (> #xFF #o77777) 'yes 'no)")).result[0])
        self.assertTrue(valCmp4.value.text == "no")

        valCmp5 = lispEvalAST(parseExpression(parseTokens("(if (= #xF 15 #b1111) 'yes 'no)")).result[0])
        self.assertTrue(valCmp5.value.text == "yes")

        valCmp6 = lispEvalAST(parseExpression(parseTokens("(if (= #xFF 12) 'yes 'no)")).result[0])
        self.assertTrue(valCmp6.value.text == "no")

        valCond1 = lispEvalAST(parseExpression(parseTokens("(cond (#f 'no))")).result[0])
        self.assertTrue(valCond1.valueType == LispValueTypes.Void)

        valCond2 = lispEvalAST(parseExpression(parseTokens("(cond (#f 'no) (#t 'yes) (#t 'maybe?))")).result[0])
        self.assertTrue(valCond2.value.text == "yes")

        valCond3 = lispEvalAST(
            parseExpression(parseTokens("(cond (#f 'no) ((< 2 1) 'oops) (else 'a 'b 'cee))")).result[0])
        self.assertTrue(valCond3.value.text == "cee")

        valCond4 = lispEvalAST(
            parseExpression(parseTokens("(cond (#f 'no) ((+ 2 2) => (lambda (x) (+ x 2))) (else 'a 'b 'cee))")).result[
                0])
        self.assertTrue(self.isEqual(valCond4.value, 6, 0))

    def testPrimitivesCoreArithmetics(self):
        val1 = lispEvalAST(parseExpression(parseTokens("(/ 3)")).result[0])
        self.assertTrue(val1.value.real.numerator == 1 and val1.value.real.denominator == 3)

        val2 = lispEvalAST(parseExpression(parseTokens("(/ 64 2 4 8)")).result[0])
        self.assertTrue(self.isEqual(val2.value, 1, 0))

    def testPrimitivesEquality(self):
        valEqv1 = lispEvalAST(
            parseExpression(parseTokens("((lambda (x) (if (eqv? 'allo x) 'yes 'no)) 'allo)")).result[0])
        self.assertTrue(valEqv1.value.text == "yes")

        valEqv2 = lispEvalAST(parseExpression(parseTokens("(eqv? \"allo\" \"allo\")")).result[0])
        self.assertTrue(valEqv2.value)

        valEqv3 = lispEvalAST(parseExpression(parseTokens("(eqv? '() '())")).result[0])
        self.assertTrue(valEqv3.value)

        valEqual1 = lispEvalAST(
            parseExpression(parseTokens("(equal? '(a b cc 1.2+i #(3 #\\d)) '(a b cc 1.2+i #(3 #\\d)))")).result[0])
        self.assertTrue(valEqual1.value)

        valEqual2 = lispEvalAST(
            parseExpression(parseTokens("(equal? '(`(#f #t . 123) c . #()) '(`(#f #t . 123) c . #()))")).result[0])
        self.assertTrue(valEqual2.value)

    def testPrimitivesPredicates(self):
        valPred1 = lispEvalAST(parseExpression(parseTokens("(number? 123.01+i)")).result[0])
        self.assertTrue(valPred1.value)

        valPred2 = lispEvalAST(parseExpression(parseTokens("(number? 'hello)")).result[0])
        self.assertFalse(valPred2.value)

        valPred3 = lispEvalAST(parseExpression(parseTokens("(char? #\\a)")).result[0])
        self.assertTrue(valPred3.value)

        valPred4 = lispEvalAST(parseExpression(parseTokens("(char? \"a\")")).result[0])
        self.assertFalse(valPred4.value)

        valPred5 = lispEvalAST(parseExpression(parseTokens("(boolean? #f)")).result[0])
        self.assertTrue(valPred5.value)

        valPred6 = lispEvalAST(parseExpression(parseTokens("(boolean? 'false)")).result[0])
        self.assertFalse(valPred6.value)

        valPred7 = lispEvalAST(parseExpression(parseTokens("(string? \"yes\")")).result[0])
        self.assertTrue(valPred7.value)

        valPred7 = lispEvalAST(parseExpression(parseTokens("(string? 'false)")).result[0])
        self.assertFalse(valPred6.value)

        valPred8 = lispEvalAST(parseExpression(parseTokens("(pair? '(a b c))")).result[0])
        self.assertTrue(valPred8.value)

        valPred9 = lispEvalAST(parseExpression(parseTokens("(pair? 'false)")).result[0])
        self.assertFalse(valPred9.value)

        valPred10 = lispEvalAST(parseExpression(parseTokens("(vector? '#(a b c))")).result[0])
        self.assertTrue(valPred10.value)

        valPred11 = lispEvalAST(parseExpression(parseTokens("(vector? '(a b c))")).result[0])
        self.assertFalse(valPred11.value)

        valPred12 = lispEvalAST(parseExpression(parseTokens("(procedure? +)")).result[0])
        self.assertTrue(valPred12.value)

        valPred13 = lispEvalAST(parseExpression(parseTokens("(procedure? '+)")).result[0])
        self.assertFalse(valPred13.value)

    def testLet(self):
        valLet1 = lispEvalAST(parseExpression(parseTokens("(let ((x 1)) (= x 1))")).result[0])
        self.assertTrue(valLet1.value)

        valLet2 = lispEvalAST(parseExpression(parseTokens("(let ((x 1) (y 2) (z 3)) (+ x y z))")).result[0])
        self.assertTrue(self.isEqual(valLet2.value, 6, 0))

        valLet3 = lispEvalAST(parseExpression(parseTokens("(let* ((x 1) (y (+ x 1))) (+ x y))")).result[0])
        self.assertTrue(self.isEqual(valLet3.value, 3, 0))

        valLet4 = lispEvalAST(parseExpression(
            parseTokens("(letrec ((fact (lambda (n) (if (<= n 1) 1 (* n (fact (- n 1))))))) (fact 4))")).result[0])
        self.assertTrue(self.isEqual(valLet4.value, 24, 0))

    def testAndOr(self):
        val1 = lispEvalAST(parseExpression(parseTokens("(and #t 1.0 (< 1 2))")).result[0])
        self.assertTrue(val1)

        val2 = lispEvalAST(parseExpression(parseTokens("(or #f (> 1 2) (+ 0 0))")).result[0])
        self.assertTrue(self.isEqual(val2.value, 0, 0))

    def testBegin(self):
        val1 = lispEvalAST(parseExpression(parseTokens("(begin 1)")).result[0])
        self.assertTrue(self.isEqual(val1.value, 1, 0))

        val2 = lispEvalAST(parseExpression(parseTokens("(begin 'a (+ 1 2) #t)")).result[0])
        self.assertTrue(val2.valueType)

    def testNumberPredicates(self):
        val1 = lispEvalAST(parseExpression(parseTokens("(complex? 1+i)")).result[0])
        self.assertTrue(val1.value)

        val2 = lispEvalAST(parseExpression(parseTokens("(complex? #xabc)")).result[0])
        self.assertTrue(val2.value)

        val3 = lispEvalAST(parseExpression(parseTokens("(real? 123e567)")).result[0])
        self.assertTrue(val3.value)

        val4 = lispEvalAST(parseExpression(parseTokens("(real? 1.135)")).result[0])
        self.assertTrue(val4.value)

        val5 = lispEvalAST(parseExpression(parseTokens("(real? #b101001)")).result[0])
        self.assertTrue(val5.value)

        val6 = lispEvalAST(parseExpression(parseTokens("(real? 1+i)")).result[0])
        self.assertFalse(val6.value)

        val7 = lispEvalAST(parseExpression(parseTokens("(rational? 12/34)")).result[0])
        self.assertTrue(val7.value)

        val8 = lispEvalAST(parseExpression(parseTokens("(rational? #x123abc)")).result[0])
        self.assertTrue(val8.value)

        val9 = lispEvalAST(parseExpression(parseTokens("(rational? 1.234)")).result[0])
        self.assertFalse(val9.value)

        val10 = lispEvalAST(parseExpression(parseTokens("(integer? 123)")).result[0])
        self.assertTrue(val10.value)

        val11 = lispEvalAST(parseExpression(parseTokens("(integer? #x123)")).result[0])
        self.assertTrue(val11.value)

        val12 = lispEvalAST(parseExpression(parseTokens("(integer? 1.234)")).result[0])
        self.assertFalse(val12.value)

        val13 = lispEvalAST(parseExpression(parseTokens("(integer? 12/34)")).result[0])
        self.assertFalse(val13.value)

        val14 = lispEvalAST(parseExpression(parseTokens("(exact? 12/34)")).result[0])
        self.assertTrue(val14.value)

        val15 = lispEvalAST(parseExpression(parseTokens("(exact? 1e10)")).result[0])
        self.assertFalse(val15.value)

        val16 = lispEvalAST(parseExpression(parseTokens("(inexact? 1.3e-5)")).result[0])
        self.assertTrue(val16.value)

        val17 = lispEvalAST(parseExpression(parseTokens("(inexact? #b1010)")).result[0])
        self.assertFalse(val17.value)

    def testOtherNumPredicates(self):
        val1 = lispEvalAST(parseExpression(parseTokens("(zero? 0e10)")).result[0])
        self.assertTrue(val1.value)

        val2 = lispEvalAST(parseExpression(parseTokens("(zero? 2+i)")).result[0])
        self.assertFalse(val2.value)

        val3 = lispEvalAST(parseExpression(parseTokens("(positive? 2.3e-55)")).result[0])
        self.assertTrue(val3.value)

        val4 = lispEvalAST(parseExpression(parseTokens("(positive? -5)")).result[0])
        self.assertFalse(val4.value)

        val5 = lispEvalAST(parseExpression(parseTokens("(negative? (- 5/6 1))")).result[0])
        self.assertTrue(val5.value)

    def testMinMaxAbs(self):
        val1 = lispEvalAST(parseExpression(parseTokens("(max 1 2 3 4 -3 -2))")).result[0])
        self.assertTrue(self.isEqual(val1.value, 4, 0))

        val2 = lispEvalAST(parseExpression(parseTokens("(min 1 2 3 4 -3 -2))")).result[0])
        self.assertTrue(self.isEqual(val2.value, -3, 0))

        val3 = lispEvalAST(parseExpression(parseTokens("(abs -10))")).result[0])
        self.assertTrue(self.isEqual(val3.value, 10, 0))

        val4 = lispEvalAST(parseExpression(parseTokens("(abs #xF))")).result[0])
        self.assertTrue(self.isEqual(val4.value, 15, 0))

        val5 = lispEvalAST(parseExpression(parseTokens("(abs -1.23))")).result[0])
        self.assertTrue(self.isEqual(val5.value, 1.23, 0))

    def testNumTheoryPrimitives(self):
        val1 = lispEvalAST(parseExpression(parseTokens("(quotient 14 3))")).result[0])
        self.assertTrue(self.isEqual(val1.value, 4, 0))

        val2 = lispEvalAST(parseExpression(parseTokens("(quotient -14 3))")).result[0])
        self.assertTrue(self.isEqual(val2.value, -4, 0))

        val3 = lispEvalAST(parseExpression(parseTokens("(remainder 13 4))")).result[0])
        self.assertTrue(self.isEqual(val3.value, 1, 0))

        val4 = lispEvalAST(parseExpression(parseTokens("(modulo 13 4))")).result[0])
        self.assertTrue(self.isEqual(val4.value, 1, 0))

        val5 = lispEvalAST(parseExpression(parseTokens("(remainder -13 4))")).result[0])
        self.assertTrue(self.isEqual(val5.value, -1, 0))

        val6 = lispEvalAST(parseExpression(parseTokens("(modulo -13 4))")).result[0])
        self.assertTrue(self.isEqual(val6.value, 3, 0))

        val7 = lispEvalAST(parseExpression(parseTokens("(remainder 13 -4))")).result[0])
        self.assertTrue(self.isEqual(val7.value, 1, 0))

        val8 = lispEvalAST(parseExpression(parseTokens("(modulo 13 -4))")).result[0])
        self.assertTrue(self.isEqual(val8.value, -3, 0))

        val9 = lispEvalAST(parseExpression(parseTokens("(remainder -13 -4))")).result[0])
        self.assertTrue(self.isEqual(val9.value, -1, 0))

        val10 = lispEvalAST(parseExpression(parseTokens("(modulo -13 -4))")).result[0])
        self.assertTrue(self.isEqual(val10.value, -1, 0))

        val11 = lispEvalAST(parseExpression(parseTokens("(remainder -13 -4.0))")).result[0])
        self.assertTrue(self.isEqual(val11.value, -1, 0))

    def testGCDLCM(self):
        val1 = lispEvalAST(parseExpression(parseTokens("(gcd 32 -36))")).result[0])
        self.assertTrue(self.isEqual(val1.value, 4, 0))

        val2 = lispEvalAST(parseExpression(parseTokens("(gcd))")).result[0])
        self.assertTrue(self.isEqual(val2.value, 0, 0))

        val3 = lispEvalAST(parseExpression(parseTokens("(lcm 32 -36))")).result[0])
        self.assertTrue(self.isEqual(val3.value, 288, 0))

        val4 = lispEvalAST(parseExpression(parseTokens("(lcm 32.0 -36))")).result[0])
        self.assertTrue(self.isEqual(val4.value, 288, 0))

        val5 = lispEvalAST(parseExpression(parseTokens("(lcm))")).result[0])
        self.assertTrue(self.isEqual(val5.value, 1, 0))

    def testNumDenom(self):
        val1 = lispEval("(numerator -5/3))")
        self.assertTrue(self.isEqual(val1.value, -5, 0))

        val2 = lispEval("(denominator -5/3))")
        self.assertTrue(self.isEqual(val2.value, 3, 0))

    def testFloorCeilingEtc(self):
        val1 = lispEval("(floor -5/3))")
        self.assertTrue(self.isEqual(val1.value, -2, 0))

        val2 = lispEval("(ceiling -5/3))")
        self.assertTrue(self.isEqual(val2.value, -1, 0))

        val3 = lispEval("(truncate -5/3))")
        self.assertTrue(self.isEqual(val3.value, -1, 0))

        val4 = lispEval("(round -5/3))")
        self.assertTrue(self.isEqual(val4.value, -2, 0))

    def testNumFuns(self):
        self.assertTrue(self.isEqual(lispEval("(exp 1))").value, 2.718281828459045, 0))
        self.assertTrue(self.isEqual(lispEval("(exp 10))").value, 22026.465794806718, 0))
        self.assertTrue(self.isEqual(lispEval("(log 2.718281828459045))").value, 1, 0))
        self.assertTrue(self.isEqual(lispEval("(/ (log 100) (log 10))").value, 2, 0))
        self.assertTrue(self.isEqual(lispEval("(sin 3.14159)").value, 0, 0))
        self.assertTrue(self.isEqual(lispEval("(sin (* 3.14159 1/2))").value, 1, 0))
        self.assertTrue(self.isEqual(lispEval("(cos 0)").value, 1, 0))
        self.assertTrue(self.isEqual(lispEval("(cos (* 3.14159 1/2))").value, 0, 0))
        self.assertTrue(self.isEqual(lispEval("(tan 3.14159)").value, 0, 0))
        self.assertTrue(lispEval("(tan (* 3.141592653589793 1/2))").value.real.getFloat() > 10e10)
        self.assertTrue(self.isEqual(lispEval("(asin 0)").value, 0, 0))
        self.assertTrue(self.isEqual(lispEval("(asin 1)").value, 3.141592653589793 * 0.5, 0))
        self.assertTrue(self.isEqual(lispEval("(acos 1)").value, 0, 0))
        self.assertTrue(self.isEqual(lispEval("(acos 0)").value, 3.141592653589793 * 0.5, 0))
        self.assertTrue(self.isEqual(lispEval("(sqrt 25)").value, 5, 0))
        self.assertTrue(self.isEqual(lispEval("(sqrt 25+9i)").value, 5.07792, 0.8861))
        self.assertTrue(self.isEqual(lispEval("(expt 2 8)").value, 256, 0))

    def testComplexNum(self):
        self.assertTrue(self.isEqual(lispEval("(make-rectangular 2 3.3)").value, 2, 3.3))
        self.assertTrue(self.isEqual(lispEval("(make-polar 2 (* 3.14159 1/4))").value, np.sqrt(2), np.sqrt(2)))
        self.assertTrue(self.isEqual(lispEval("(real-part 3+2i)").value, 3, 0))
        self.assertTrue(self.isEqual(lispEval("(imag-part 3+2i)").value, 2, 0))
        self.assertTrue(self.isEqual(lispEval("(magnitude 10+10i)").value, np.sqrt(2) * 10, 0))
        self.assertTrue(self.isEqual(lispEval("(angle 10+10i)").value, np.pi * 0.25, 0))

    def testExactnessConvertion(self):
        self.assertTrue(self.isEqual(lispEval("(exact->inexact 0.5)").value, 0.5, 0))
        self.assertTrue(self.isEqual(lispEval("(exact->inexact 1/2)").value, 0.5, 0))
        v = lispEval("(inexact->exact 0.5)").value
        self.assertTrue(v.real.getInt() == 1 and v.real.denominator == 2)

    def testNumStrConversions(self):
        self.assertTrue(lispEval("(number->string 1/2)").value.extra == "1/2")
        self.assertTrue(lispEval("(number->string 1/2+i)").value.extra == "1/2+1i")
        self.assertTrue(lispEval("(number->string 0.5e3)").value.extra == "500.0")
        self.assertTrue(lispEval("(number->string 0.123e-3+0.2i)").value.extra == "0.000123+0.2i")
        self.assertTrue(self.isEqual(lispEval("(string->number \"1/2\")").value, 0.5, 0))
        self.assertTrue(self.isEqual(lispEval("(string->number \"0.123+2e3i\")").value, 0.123, 2000))


def runLispTests():
    unittest.TestLoader().loadTestsFromTestCase(TestLispLex).run(
        unittest.TextTestRunner(sys.stdout, True, 1).run(unittest.TestLoader().loadTestsFromTestCase(TestLispLex)))
