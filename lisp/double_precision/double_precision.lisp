(defvar MAX 2147483647) ; 2^31 - 1

(defvar a-high 0)
(defvar a-low 2147483647) ; 2^31 - 1

(defvar b-high 0)
(defvar b-low 2147483647) ; 2^31 - 1

(defvar res-high 0) ; 1
(defvar res-low 0) ; 2^31 - 1
(defvar carry 0)

(defun print-num-rec (n)
  (if (> n 0) (print-num-rec (/ n 10)) 0)
  (if (> n 0) (out 1 (+ (mod n 10) 48)) 0)
)

(defun print-num (n)
  (if (= n 0) (out 1 48) (print-num-rec n))
)

(defun add-64 ()
  (if (> a-low (- MAX b-low))
      (if (setq carry 1)
          (setq res-low (- (+ a-low b-low) (+ MAX 1)))
          0)
      (if (setq carry 0)
          (setq res-low (+ a-low b-low)) 
          0)
  )
  
  (setq res-high (+ (+ a-high b-high) carry))
)

(print "\n")
(add-64)
(print "  High Word: ")
(print-num res-high)
(print "\n  Low Word:  ")
(print-num res-low)