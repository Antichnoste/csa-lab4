(defvar char 0)
(defvar ptr 0)

(defun read-name (rn-addr)
  (setq ptr rn-addr)
  (loop
    (setq char (in 0))
    (if (= char 0) (write-mem ptr 0) 0) ; ПИШЕМ ТЕРМИНАТОР!
    (if (= char 0) (return 0) 0) ; И только потом выходим из функции
    (write-mem ptr char)
    (setq ptr (+ ptr 1))
  )
)

(defun print-mem (pm-addr)
  (setq ptr pm-addr)
  (loop
    (setq char (read-mem ptr))
    (if (= char 0) (return 0) 0)
    (out 1 char)
    (setq ptr (+ ptr 1))
  )
)

(print "What is your name?\n")
(read-name 5000)
(print "Hello, ")
(print-mem 5000)
(print "!")