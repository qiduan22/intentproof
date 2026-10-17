(set-logic QF_BV)
; This is a source-grounded post-reset snapshot, not an RTL elaboration.
(declare-fun arvalid () (_ BitVec 2))
; Original: registered ARREADY, reset to zero and still zero at first sampled active cycle.
(define-fun real_ready () (_ BitVec 2) #b00)
; Candidate: idle=0; turn=0; combinational ready for request chosen at this cycle.
(define-fun abstract_ready () (_ BitVec 2)
    (ite (= arvalid #b00) #b00
         (ite (= ((_ extract 0 0) arvalid) #b1) #b01 #b10)))
(define-fun real_accept () (_ BitVec 2) (bvand arvalid real_ready))
(define-fun abstract_accept () (_ BitVec 2) (bvand arvalid abstract_ready))
(assert (not (= real_accept abstract_accept)))
(assert (= arvalid #b00))
(check-sat)
