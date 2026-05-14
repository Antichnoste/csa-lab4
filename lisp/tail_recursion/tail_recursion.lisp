(defun tail_recursion_loop (i)
    (print (+ i 48))
    (if (= i 0)
        (return 0)
        (tail_recursion_loop (- i 1)))
)

(tail_recursion_loop 9)
