(defvar pn-rev 0)
(defvar pn-count 0)
(defvar pn-rem 0)

(defun print-num-rec (n)
  (if (> n 0)
      (print-num-rec (/ n 10))
      0)
  (if (> n 0)
      (out 1 (+ (mod n 10) 48))
      0)
)

(defun print-num (n)
  (if (= n 0)
      (out 1 48)
      (print-num-rec n)
  )
)

(defvar rev-rev 0)
(defun reverse (rev-n)
  (setq rev-rev 0)
  (loop
    (if (= rev-n 0) (return rev-rev) 0)
    (setq rev-rev (+ (* rev-rev 10) (mod rev-n 10)))
    (setq rev-n (/ rev-n 10))
  )
)

(defvar max-pal 0)
(defvar prod 0)

(defun inner-loop (il-i il-j)
  (loop
    (if (< il-j il-i) (return 0) 0)
    (setq prod (* il-i il-j))
    (if (< prod max-pal) (return 0) 0)
    
    (if (= prod (reverse prod))
        (setq max-pal prod)
        0)
    (setq il-j (- il-j 1))
  )
)

(defun solve (slv-i)
  (setq max-pal 0)
  (loop
    (if (< slv-i 100) (return max-pal) 0)
    (inner-loop slv-i 999)
    (setq slv-i (- slv-i 1))
  )
)

(print-num (solve 999))