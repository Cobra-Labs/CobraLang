## Documented Errors in Cobra 1.0

---

### E1: SyntaxError

This Error is risen if the Syntax is incorrect. 

```cobralang
# Example:
dee main() -> i32:
^^^ 'dee' is not valid. 'def' is valid
```

---

### E2: KeyError

This Error is risen if an object is simply not existing - not as ident nor a variable.

```cobralang
# Example:
i = keywords[x]
#            ^ 'x' is non existing / invalid
```

---

### E3: TypeMismatchError

This error is raised if a variable is initialized, assigned, or used in an arithmetic calculation with a different datatype than declared. Cobra does not perform implicit type conversion.

```cobralang
# Example:
let x: i32 = 0
let y: i64 = 65535

let z: i32 = x + y
#   ^^^^^^       ^ Error: 'z' is i32, but 'y' is i64. 
#                  Hint: Use 'y as i32' for explicit casting.
```

---

### E4: UnresolvedSymbolError

This Error is raised if a variable is used but never initialized with a value. 

```cobralang
# Example:
let x: i32 = y + 12
#            ^ 'y' was never declared nor initialized
```

---

### E5: ArgumentCountError

This Error is raised if a function is called with an invalid number of arguments.

```cobralang
# Example:
def foo(a: i32, b: ptr<u8>) -> i32:
    ...
    
foo(4)
#   ^ 'foo' takes 2 arguments, but only one was supplied
```

---

### E6: 