(defvar char 0)

(defun cat ()
  (loop
    (setq char (in 0))
    (if (= char 0) (return 0) 0)
    (out 1 char)
  )
)

(cat)