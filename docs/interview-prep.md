# Interview preparation — AI Proposal Generator

Answers to the questions an interviewer is likely to ask about this project.
Written in plain English (B1–B2) but technically precise. Each answer is true to
the code; none over-claims.

---

### 1. Why can't prices be trusted to the LLM?

Language models predict text. They can copy a number wrong, round it, or invent
one, and they do this confidently. In a commercial proposal a wrong price is a
real business problem. So I keep every number out of the model completely: the
prompt contains product *names* only, and the total is computed in Python from
the input file. The model writes sentences; the code owns the money. That makes
a wrong number impossible, instead of just unlikely.

### 2. Why `Decimal` and not `float`?

Money must be exact. `float` uses binary fractions, so values like `0.1 + 0.2`
do not come out exactly right, and errors add up over many items. `Decimal`
stores base-10 numbers exactly, so prices and totals are correct to the cent. I
also enforce two decimal places at the input boundary, so a strange value like
`10.005` is rejected before it can break the displayed arithmetic.

### 3. Why do the model's reply items need explicit indices?

Because I must match each description to the *right* product. If I matched by
position in the list, and the model dropped one product or reordered them, I
would silently pair the wrong description with the wrong price. Instead, each
item in the reply must carry an explicit index, and I reject the whole reply
unless the indices are exactly `0` to `N-1`, each once, in order. A wrong reply
fails loudly instead of producing a wrong document.

### 4. How are transport retries different from content repair?

They fix different problems. **Transport retries** (handled by the SDK) are for
network trouble — a timeout, a 503, a rate limit. The request was fine; the
network was not, so you resend the same request. **Content repair** is for a
reply that arrived successfully but broke my contract — bad JSON, or missing a
product. There, resending the same prompt would not help, so I send a new prompt
that includes the model's bad reply and the validation error, and ask it to fix
it — once. Different causes, different fixes, separate settings.

### 5. What does JSON mode guarantee, and what does it not?

JSON mode (`response_format`) tells the provider to return syntactically valid
JSON, so I get far fewer "this isn't even JSON" errors. What it does **not**
guarantee is that the JSON *means* the right thing — it can still miss a product,
duplicate one, or get truncated if the reply is long. That semantic contract is
my job: I validate the parsed reply against the index rules. JSON mode shrinks
one class of failure; my validation and the repair loop handle the rest. Because
some providers reject the parameter, the code falls back to prompt-only JSON if
it is not supported.

### 6. How is the project protected from HTML injection?

The proposal is HTML rendered to PDF, and both the client data (from an
untrusted YAML file) and the model's prose end up in that HTML. I render with
Jinja2 `autoescape=True`, so any HTML characters in that text are escaped and
shown as text, never executed. I also use `StrictUndefined`, so a missing
template variable is a loud error rather than silent empty output. Both paths
have tests.

### 7. How is an invalid model response handled?

Every bad reply becomes a controlled, typed failure — never a crash or a wrong
document. If the JSON does not parse, or a citation index is wrong, or a
description is empty, the reply is rejected. The repair loop then gets one chance
to fix it. If it still fails, the program exits with code `69` (the "LLM/service"
class) and a clear message. Nothing partial is written.

### 8. Why don't the tests use a real API?

Three reasons: speed, determinism, and cost. A test that calls a real model is
slow, can give a different answer each run, and needs a paid key — so it cannot
run in CI for every push. Instead I replace the model with a `FakeProvider` that
replays a saved, realistic reply. All 162 tests run offline with no key and no
network, which is why they are safe to run on every commit and on three
operating systems.

### 9. Why do you need live evals if you already have unit tests?

They answer different questions. Unit tests prove the *plumbing* works — parsing,
validation, rendering — using a fixed fake reply. They cannot tell me whether a
*real* model, today, still produces good, grounded output. Live evals run real
inputs against the real model and score the results. Tests catch regressions in
my code; evals catch regressions in the model's behavior and in the prompt.

### 10. How is the quality of generated prose measured?

With automated checks, honestly scoped. On every generated reply the eval scores
four things: the language matches the input, each section is within sensible
length bounds, no number appears in the prose that was not in the input, and
there are no stray markdown artifacts. These are checkable heuristics. What they
do **not** measure is whether the writing is persuasive — that still needs a
human or an LLM judge, and I say so rather than pretend a heuristic covers it.

### 11. What are the limitations of the current evals?

The checks are structural and heuristic, not semantic — they confirm the reply
is safe and well-formed, not that it will actually win a customer. The live run
is a small sample (30 calls), so the pass/fail counts show direction, not a
statistical proof. And the live eval needs a real key, so it runs on a schedule,
not on every push. The offline checks that *do* run in CI are deterministic and
need no key.

### 12. Why Chrome for PDF generation?

The template uses real web fonts and modern CSS. Headless Chrome renders it
exactly the way a browser would, with no native Python dependencies to fight.
Pure-Python PDF libraries would need me to simplify the design and still might
render it differently. The cost of using Chrome is an external binary, which I
solved for reproducibility by bundling Chromium in the Docker image. I also
verify the output is a real, non-empty PDF before reporting success.

### 13. How could the project scale to other document types?

The architecture already separates "prose from the model" from "numbers and
structure from the data," so a new document type — an invoice or an estimate —
reuses the same spine: a new input schema, a new prompt, a new template, and the
same validation and rendering. The one hard rule carries over: the model writes
text, the code owns the numbers.

### 14. What would production deployment require?

For a real product I would add: a proper interface (an API endpoint or a bot)
in front of the CLI; asynchronous handling and a queue if volume is high;
provider rate-limit and cost controls beyond the SDK's retries; secret
management through the platform rather than a `.env` file; and log aggregation.
The contracts, typed errors, tests, and evals that already exist are what make
that step safe rather than risky — they are the hard part, and they are done.

### 15. How is prompt-injection risk limited?

It is **bounded, not prevented**, and I state that clearly. A hostile product or
client name flows into the prompt and could influence the *prose* — for example,
push the model toward an odd sentence. What it cannot do: change any number
(numbers never go through the model), break the document structure (the reply
must pass the strict index contract or the run fails), inject HTML (autoescape),
or leak a secret (none are in the prompt). The worst case is a strange sentence
in a document a human reviews before sending — and the eval checks flag invented
numbers on top of that.
