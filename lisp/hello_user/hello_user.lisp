(defvar ch 0)
(defvar prompt "What is your name?\n")
(defvar hello "Hello,")
(defvar suffix "!\n")

(defun read_name_loop ()
  (loop
    (setq ch (in 0))
    (if (= ch 10)
        (return 0)
        (out 0 ch))))

(print prompt)
(print hello)
(read_name_loop)
(print suffix)
