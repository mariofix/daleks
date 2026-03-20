# Language options for Daleks

> Prompted by the question: *"I don't think interpreted languages are the best fit
> for these types of services — options?"*

---

## Does being interpreted actually hurt here?

Daleks is an **I/O-bound** service: every request immediately parks in a queue
and every worker immediately blocks on a network socket waiting for an SMTP
handshake.  The CPU does almost nothing.

That matters because Python's two most-cited costs—interpretation overhead and
the Global Interpreter Lock (GIL)—are largely irrelevant for I/O-bound work:

| Concern | Reality for Daleks |
|---|---|
| Slow bytecode execution | The hot path is `queue.put_nowait()` + `await aiosmtplib.send()`. The SMTP round-trip (100s–1000s ms) dwarfs Python's overhead. |
| GIL blocks parallelism | `asyncio` coroutines yield the GIL on every `await`, so concurrent workers run fine inside one process. |
| High memory footprint | Real — CPython baseline is ~25–40 MB per process vs ~5–10 MB for a Go binary. Matters if you run dozens of instances. |
| Slow cold start | Real — ~300–500 ms for CPython+FastAPI vs ~5 ms for a compiled binary. Matters for containers that restart frequently. |

**Short answer**: Python asyncio is a defensible choice for this specific
workload.  You will notice the difference mainly in memory usage and container
startup time, not in email throughput.

---

## Compiled-language alternatives

### Go (recommended if you want to rewrite)

Go's concurrency primitives (`goroutines` + `channels`) map 1-to-1 onto
Daleks' architecture (one channel per SMTP account, N goroutine workers draining
it).  Relevant standard-library and ecosystem packages:

| Python package | Go equivalent |
|---|---|
| `fastapi` | `net/http` (stdlib) or [`chi`](https://github.com/go-chi/chi) / [`gin`](https://github.com/gin-gonic/gin) |
| `uvicorn` | Built into the binary — no separate server needed |
| `pydantic` | [`encoding/json`](https://pkg.go.dev/encoding/json) + struct tags |
| `aiosmtplib` | [`net/smtp`](https://pkg.go.dev/net/smtp) (stdlib) |
| `tomllib` | [`github.com/BurntSushi/toml`](https://github.com/BurntSushi/toml) |

**Wins**: ~10× lower memory, <10 ms cold start, single static binary, no
runtime to install, safe concurrency.

**Trade-off**: More boilerplate; no automatic request validation like Pydantic.

---

### Rust

Maximum raw performance and memory safety enforced at compile time.  The async
ecosystem (`tokio` runtime, `axum` web framework, `lettre` SMTP library) is
mature.

**Wins**: Lowest possible memory and CPU overhead, no garbage-collector pauses.

**Trade-off**: Steeper learning curve; longer compile times; more complex error
handling.  Likely overkill for a service whose bottleneck is external SMTP
latency.

---

### Elixir / Erlang (BEAM)

Not compiled to machine code, but compiled to BEAM bytecode which runs on the
highly optimised Erlang VM.  The actor model and OTP supervision trees are a
natural fit for queue-worker patterns.

**Wins**: Fault-tolerant by design; hot code reloading; millions of lightweight
processes; built-in distributed primitives.

**Trade-off**: Small ecosystem for SMTP compared to Go/Rust; different
programming paradigm.

---

## Quick comparison

| | Python (current) | Go | Rust | Elixir |
|---|---|---|---|---|
| Execution | Interpreted (CPython) | Compiled (native) | Compiled (native) | BEAM bytecode |
| Memory (idle) | ~30–40 MB | ~5–10 MB | ~2–5 MB | ~15–25 MB |
| Cold start | ~400 ms | ~5 ms | ~5 ms | ~100 ms |
| Concurrency model | asyncio event loop | goroutines + channels | tokio async tasks | BEAM processes |
| SMTP library maturity | ✅ aiosmtplib | ✅ net/smtp (stdlib) | ✅ lettre | ⚠ moderate |
| Deployment | virtualenv / pip | single static binary | single static binary | Erlang runtime |
| Code volume for this service | ~400 LOC | ~400 LOC | ~600 LOC | ~300 LOC |

---

## Recommendation

- **Keep Python** if the team is comfortable with it and memory/startup time are
  not constraints.  The asyncio architecture is sound for this workload.
- **Rewrite in Go** if you need a smaller container image, faster restarts, or
  lower per-instance memory — and you want the shortest migration path because
  the channel/goroutine model mirrors the current asyncio/queue design almost
  exactly.
- **Rewrite in Rust** only if you have extreme throughput or memory requirements
  and the team has Rust experience.
- **Consider Elixir** if resilience and hot-reload matter more than raw
  performance (e.g. you never want to drop queued emails during a deploy).
