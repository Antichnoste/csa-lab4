(defvar p 1)
(defvar x 0)

(defun print-num-rec (n)
  (if (> n 0) (print-num-rec (/ n 10)) 0)
  (if (> n 0) (out 1 (+ (mod n 10) 48)) 0))

(defun print-num (n)
  (if (= n 0) (out 1 48) (print-num-rec n)))

(print "\n    1+2+3+4 = ")
(print-num (+ 1 2 3 4))
(print "\n")

; проверка 'if' как выражения
(print "    If as expression: ")
(print-num (if p 111 222))
(print "\n")

; проверка 'setq' как выражения
(print "    (5 + (x=10)) = ")
(print-num (+ 5 (setq x 10)))
(print "\n")

; любое не-ноль число = true
(print "    if 5 is true: ")
(if 5
    (print "OK") 
    (print "FAIL"))
(print "\n")

(print "    (1+2)*(10-5) = ")
(print-num (* (+ 1 2) (- 10 5)))