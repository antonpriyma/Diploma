from parse_utils.lispInterpreter import lispEval, parseTokens

if __name__ == '__main__':
    code = """(define error 1)

(define (operator? a)
  (member a '(#\+ #\- #\/ #\* #\^)))

(define (constant? a)
  (and (> (char->integer a) 47)
       (< (char->integer a) 58)))

(define (variable? a)
  (and (> (char->integer a) 96)
       (< (char->integer a) 123)))

(define (paranthesis? a)
  (or (equal? a #\()
      (equal? a #\))))

(define (delimiter? a)
  (or (equal? a #\space)
      (equal? a #\newline)
      (equal? a #\tab)))

(define (return-constant str)
  (define (f a a1)
    (cond ((null? a) a)
          ((constant? (car a)) (f (cdr a) (cdr a1)))
          ((equal? (car a) #\E) (f (cdr a) (cdr a1)))
          ((equal? (car a) #\e) (f (cdr a) (cdr a1)))
          ((and (member (car a) '(#\+ #\-))
                (or (equal? (car a1) #\e)
                    (equal? (car a1) #\E))) (f (cdr a) (cdr a1)))     
          ((equal? (car a) #\.) (f (cdr a) (cdr a1)))
          (else a)))
  (f str (append '(#\() str)))


(define (return-variable str)
  (define (f a)
    (cond ((null? a) a)
          ((variable? (car a)) (return-variable (cdr a)))
          (else a)))
  (f str))


(define (tokenize str)
  (define (f a res)
    (cond ((null? a) (reverse res))
          ((operator? (car a)) (f (cdr a) (cons (string->symbol (string (car a))) res)))
          ((constant? (car a)) (f (return-constant a) (cons (string->number (list->string (substring+ a (car a) (return-constant a)))) res)))
          ((paranthesis? (car a)) (f (cdr a) (cons (string (car a)) res)))
          ((variable? (car a)) (f (return-variable a) (cons (string->symbol (list->string (substring+ a (car a) (return-variable a)))) res)))
          ((delimiter? (car a)) (f (cdr a) res))
          (else #f)))
  (f (string->list str) '()))

(define (substring+ str a b)
  (define (f e r g res i)
    (cond ((null? e) (reverse res)) 
          ((and (equal? (car e) r) (= i 0)) (f (cdr e) r g (cons (car e) '()) 1))
          ((and (equal? e g) (= i 1)) (f '() r g res 1))
          ((not (null? res)) (f (cdr e) r g (cons (car e) res) 1))))
  (f str a b '() 0))

(define (parse tokens)
  (define (peek) (if (null? tokens) #f (car tokens)))
  (define (next)
    (let ((answer (peek)))
      (if answer
          (set! tokens (cdr tokens)))
      answer))
  
  (define (parse-expr)
    
    (define (helper buffer)
      (let ((lx (peek)))
        (if (member lx '(+ -))
            (helper (list buffer (next) (parse-term)))
            buffer)))
    
    (helper (parse-term)))
  
  (define (parse-term)
    
    (define (helper buffer)
      (let ((lx (peek)))
        (if (member lx '(* /))
            (helper (list buffer (next) (parse-power)))
            buffer)))
    

    (helper (parse-power)))
  
  (define (parse-power)
    (let ((buffer (parse-factor)))
      (if (equal? (peek) '^)
          (list buffer (next) (parse-power))
          buffer)))
  
  (define (parse-factor)
    (let ((lx (next)))
      (cond ((number? lx) lx)
            ((equal? lx "(") (let ((answer (parse-expr)))
                               (if (equal? (next) ")")
                                   answer
                                   (error #f))))
            ((equal? lx '-) (list '- (parse-factor)))
            ((and (symbol? lx) (not (member lx '(+ * / =)))) lx)
            (else (error #f)))))
  
  (call-with-current-continuation
   (lambda (exit) 
     (set! error exit)
     (let ((answer (parse-expr)))
       (and (not (next)) answer)))))

(define (tree->scheme expr)
  (if (and (list? expr) (= (length expr) 3))
      (let ((x (car expr))
            (op (cadr expr))
            (y (caddr expr)))
        (list (or (and (equal? op '^) 'expt) op) (tree->scheme x) (tree->scheme y)))
      expr))"""

    res = parseTokens(code)

    print(res)