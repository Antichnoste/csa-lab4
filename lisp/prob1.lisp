(defun reverse (n)
  (defvar rev 0)
  (defvar temp n)
  (loop
    (if (= temp 0)
        (return rev)
        (setq rev (+ (* rev 10) (mod temp 10))))
    (setq temp (/ temp 10))))

(defun solve ()
  (defvar max_pal 0)
  (defvar i 999)
  (defvar j 0)
  (defvar prod 0)
  (loop
    (if (< i 100)
        (return max_pal)
        0) ; ветка else
    (setq j 999)
    (loop
      (if (< j i)
          (return 0) ; выход из внутреннего цикла
          0)
      (setq prod (* i j))
      (if (= prod (reverse prod))
          (if (> prod max_pal)
              (setq max_pal prod)
              0)
          0)
      (setq j (- j 1)))
    (setq i (- i 1))))

(out 1 (solve))