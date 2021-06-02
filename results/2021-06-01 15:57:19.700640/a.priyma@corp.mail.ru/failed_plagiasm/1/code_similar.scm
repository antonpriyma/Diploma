#lang racket

(define (my-gcd x y)
  (if (= x y)
      x
      (if (> x y)
          (my-gcd (- x y) y)
          (my-gcd (- y x) x))))

(define (my-lcm x y)
  (/ (* x y) (my-gcd x y)))

(define (prime? n)
  (define (plus a)
    (cond
      ((= n 0) #f)
      ((> a (sqrt n)) #t)
      (else (if (not (= (remainder n a) 0))
                (plus (+ a 1))
                #f))))
  (plus 2))


