# Stream (WIP)

Stream is a tiny stream-centric language where programs are pipelines and behavior is described as *flow*.

The interpreter is `sti`. A Stream program is a text file (commonly `*.program`) that defines:
- optional metadata (season, drift)
- gyge bindings (imports / builtins)
- a single entrypoint called `spring`

## Hello, world

```stream
<-> Hello, Stream!

gyge stdout -:> <o>::fd::stdout;

season -:> spring;
drift -:> gentle;

spring -:> {
  "Hello, world!" -> stdout
}
```

### What this means
#### Comments
- `<->` starts a comment line:
- `<->` This is a comment

#### Imports / bindings (gyge)
A gyge is a named node/operator you can use in the program.
You bind a gyge name to an imported symbol:
```stream
gyge stdout -:> <o>::fd::stdout;
```
Where `stdout` is the gyge name used in your pipeline.
- `<o>` is a module meaning “this process” (a safe, process-scoped OS surface)

- `::` traverses namespaces inside that module.:
`<o>::fd::stdout` resolves to a callable sink that prints to standard output

### Season and drift
These are program-level modifiers:
```stream
season -:> spring;
drift  -:> gentle;
```
They are currently metadata (and/or runtime policy knobs), and are intended to influence scheduling/behavior as the language grows.

### Entrypoint and pipelines
Every program starts at a season:
```stream
spring -:> { ... }
```
### Running
From the project root:
```shell
uv run python -m sti path/to/hello.program
```
Or, if you expose a CLI entrypoint (recommended):
```shell
uv run sti path/to/hello.st
```
### Current status
This project is intentionally small and evolving:

The syntax is stabilized around gyge, season/drift, spring, and ->.

The import model uses `<module>::path::symbol`.

More stream operators (=>, ~>, filters, pack/unpack, errors/signals) will arrive as the interpreter grows.