⟨⟨ Hello, Stream!

   The simplest possible Stream program.
   One gyge holds a string literal; it flows through a single ⟶ edge
   into the built-in ⌈print⌉ gyge.

   Expected output:
       Hello, Stream!
⟩⟩

§header§
    <o⟶ "hello"

§body§
    ⌈greeting⌉ ≔ "Hello, Stream!"
    ⌈greeting⌉ ⟶ ⌈print⌉
