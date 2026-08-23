# How this was actually done

One person, an agent, one desktop, and a lab notebook.

[EXPLORING.md](../EXPLORING.md) is the findings. This is the process that produced them,
written down because the process transfers and the findings mostly do not: they are facts
about one GPU. If you have different hardware, none of the numbers are yours, but every
trap in Part II of that document is waiting for you anyway.

This is also, deliberately, an honest account of working with an AI agent on a research
programme rather than on a feature. Most of what is written about that is either marketing
or dismissal. This is neither. The agent made the programme possible at this scale and it
also generated a specific, recognisable class of error that ordinary code review does not
catch. Both halves are here.

Nothing in this document is a recommendation to work this way. It is a description of how
one setup worked, what it cost, and where it broke.

---

## The setup

One Framework Desktop (Ryzen AI Max+ 395, 64 GB, Radeon 8060S), a second machine used as a
cross-vendor control, a Windows box with an NVIDIA card used as a second control, and an
agent with shell access to all of it. No team, no lab, no budget beyond the hardware. The
work ran from roughly May to August 2026.

The output, so the scale is concrete: 1197 recorded benchmark runs, **one change merged
into llama.cpp itself** with several more staged behind it, a published fork and container
image with an active downstream user base, two per-dispatch trace exporters that did not
previously exist, a driver extension prototype, and about eighty separate written findings
of which the majority are negative results.

That upstream count is deliberately stated as one rather than rounded up. Most of the work
lives in a fork, some of it is calibrated too narrowly to belong upstream at all, and the
queue moves at one pull request at a time by the project's own request. Conflating "we
shipped it" with "it is in llama.cpp" is the easiest way for a project like this to
mislead people, including itself.

The thing that made this work is not the agent's ability to write code. It is that a
research programme has a **memory problem** long before it has a coding problem. Sixty
investigations over four months, each one producing three findings and two retractions, is
more state than one person holds. The interesting part of this setup is how that state was
kept.

---

## Three layers of record

### Layer 1: raw artifacts, which are never edited

Every benchmark goes through one script, and that script writes three files keyed by a
single run id:

- `<id>.meta` - timestamp, label, binary path, the binary's full version output, every
  `GGML_*` and `VK_*` environment variable, the exact argv, kernel IOMMU state, free
  memory, whether any other process held GPU memory while the run went out, how long it
  waited for the GPU lock, and the exit code.
- `<id>.raw` - verbatim, unfiltered stdout and stderr, including the device
  initialisation lines.
- `<id>.json` - the machine-readable benchmark output, which is what graphs are built from.

Plus one row in a tab-separated index.

The rule: **no claim that cannot be reconstructed from the raw artifact alone.** If a
number cannot be traced back to a `.raw` file, it does not go in a report.

This is more valuable than it sounds, and the reason is specific to working with an agent:
a conversational summary is lossy in a way that is invisible at the time and irreversible
afterwards. Several times a distilled table in a conversation was misleading until the raw
log was re-read: a per-op sum computed over unequal graph counts, a "byte identical"
comparison that was actually a missing binary, a clean-looking null A/B that turned out to
be an override aimed at a code path that never ran.

None of those were detectable from the summary. All of them were obvious in the raw output.

The `.meta` file earns its keep separately, because it is what lets you re-audit a
six-week-old number when a new result contradicts it. Roughly a third of the retractions in
Part IV of EXPLORING.md were found by going back to a `.meta` and noticing something in the
environment that nobody was thinking about at the time.

Two things the `.meta` still does not capture, which is an open gap: system load average
and compiler process count. A concurrent build costs about 7% and leaves no trace in any
field we record.

### Layer 2: derived documents, which cite run ids

Analysis lives in dated write-ups that cite the run ids they were computed from, and where
possible embed the script that regenerates the table. Tables are mechanically derived, not
transcribed. The distinction matters: a hand-copied table is a claim, a generated one is a
view.

### Layer 3: memory, one fact per file

This is the layer that makes the whole thing work across months, and it is the one most
worth stealing.

Each finding is a single small file with structured front matter and a body. One fact per
file. A short description line that is written to be read *by a retrieval process deciding
whether this is relevant*, not by a human browsing. Files link to each other by name, and a
link to a file that does not exist yet is fine, because it marks something worth writing
later.

Types we use: `project` (ongoing work and its state), `reference` (a durable fact about
some external thing), `feedback` (a correction or a confirmed working practice, always with
the reason), and `user` (context about the person, so the agent does not re-ask).

An index file with one line per memory is loaded at the start of every session. The bodies
are not; they are pulled in when relevant.

Four properties of this scheme did the actual work:

**One fact per file makes contradiction visible.** When a new measurement contradicts an old
one, there is exactly one file to open and correct. Findings written as long documents rot
silently, because the contradicting sentence is on page four and nobody re-reads page four.

**Memories are edited in place, including with their own history.** Look at almost any entry
behind EXPLORING.md and you will find a stack of dated corrections: the original finding,
then "SUPERSEDED", then "RESOLVED, and it is three mechanisms not one", then "RETRACTED, and
here is what we should have noticed". That accumulated argument is the most valuable content
in the whole system. It is what stops the same wrong idea being re-proposed in month three,
and it is why Part IV of EXPLORING.md could be written at all.

**Every finding carries a "how to apply" line.** Not just what is true, but what to do
differently. `bench-counterbalance-order` does not say "position effects exist", it says
"use A-B-B-A, and when one arm's spread is much larger than the other's, suspect position
before suspecting code". A finding without an action is not retrievable in the moment you
need it.

**Explicit do-not-claim lists.** Several memories end with a list of things the evidence does
*not* support, and those lists get consulted before anything is published. This is the single
highest-leverage habit in the whole system, because the failure mode of an agent writing up a
result is over-claiming, not under-claiming, and a pre-committed boundary is much easier to
enforce than a judgement call made while drafting.

**One thing to be careful about:** a recalled memory reflects what was true when it was
written. If it names a file, a function, or a flag, verify it still exists before acting on
it. We have chased a couple of ghosts this way.

---

## How the agent actually fails

This is the section that does not exist elsewhere and it is why this document was written.

The agent did not fail by writing buggy code. Buggy code is caught by compilers, tests, and
perplexity runs, all of which are cheap and were always on. It failed in ways that produce
**confident, plausible, well-formatted wrongness** that survives every automated check,
because the automated checks are all pointed at the code and the error is in the reasoning
or in the record.

### 1. It invents plausible workflow steps

The most important one. An earlier revision of EXPLORING.md listed, in a section headed
"what we actually do", a profiling step using a vendor GPU tool. It was a completely
reasonable-sounding step. It had never been done. There were no capture files anywhere on
the machine, the enabling environment variable appeared in none of the 393 recorded runs,
and on this driver the capture is not even possible for a headless workload.

Nobody wrote a false sentence on purpose. The agent was describing a workflow that *should*
exist, and the prose came out indistinguishable from a description of one that does.

A reader spotted the section as machine-written and asked how we ran the tool. That is how
it surfaced.

The rule that came out of it, and it is the single most useful rule here:

> **Before writing "we do X" in anything public, grep for the artifact X would have left.
> If it left none, either say so or cut the step.**

This applies to tools, workflows and rationales exactly as much as to numbers. A number gets
checked because it looks like a claim. A workflow description does not look like a claim, and
that is precisely what makes it dangerous.

Notice also the failure mode of the review process: a correctness review of that text would
have passed it, because every individual sentence was true *about the tool*. The falsehood
was in the sentence "we do this", which is a claim about the world, not about the software.

### 2. It replaces raw output with a tidy table

Constantly, and helpfully, and it costs you the ability to check anything. The
countermeasure is structural rather than behavioural: the artifact requirement above, plus
an explicit standing instruction that measured results are delivered as raw tool output and
derived tables are separate files that cite run ids.

For the change currently staged for upstream, the evidence bundle carries a verbatim
presentation round alongside the computed summary: a driver script that re-runs the arms
and captures the actual command output to files, so the prose can quote a file rather than
a conversation. It is uglier and it is checkable. Stated as one bundle rather than as
standing practice, because that is what exists on disk.

### 3. It builds a causal story out of a correlation, immediately and fluently

Every item in Part IV of EXPLORING.md is an instance. The channel-camping explanation for
the ubatch decline is the cleanest: a real mechanism, a real measurement (7.30 GB/s at that
stride), a real threshold crossing at exactly the right batch size, and a completely wrong
causal conclusion.

What fixed it was not scepticism, it was a habit: **design the measurement that would
discriminate, not the one that would confirm.** Halving the operand so it fits in cache is a
one-line experiment whose two outcomes mean opposite things. It took an hour and killed the
theory the same day it was proposed.

The general form: when the agent produces an explanation, the next question is never "is
that plausible" (it always is) but "what would we see if it were false, and can we go and
look at that today".

### 4. It reports a two-sample result with the same confidence as a twelve-sample one

A wave32 change read -0.2% and -1.2% on MoE at two launches per arm. At six launches per arm
it is +0.2% and +0.8%, inside the noise. **The two-sample reading had the wrong sign**, and
nothing in its presentation distinguished it from a settled result.

This is not an agent-specific statistical failing so much as an agent-specific *presentation*
failing: the output looked identical either way. The countermeasure is a hard rule that the
number of launches per arm appears next to any delta, and that anything under a threshold
(about 1.3x for isolated op benchmarks, about 3% end to end on this box) is reported as
unresolved rather than as a small effect.

### 5. Several sessions, one machine, and the resulting concurrency bugs

Work often ran as several parallel sessions. The failure modes are exactly the ones you would
expect from threads sharing mutable state, and they are worth listing because they are not
obvious in advance:

- **A shared working tree.** One session's `git add <file> && git commit` swept another
  session's uncommitted work into a commit whose message described only the intended change,
  and it was pushed to a public fork. Committing by filename stages everything in that file.
- **A commit race.** A clean status check passed, another session committed eight seconds
  later, and a cherry-pick landed on top of it without warning. Caught only by an
  outgoing-commit count at push time.
- **A shared GPU.** Solved with an exclusive lock that benchmarks take and wait up to two
  hours for. Not solved for compiles, which take no lock and cost about 7%.
- **A shared page cache.** Two campaigns holding 60 GB of weights between them on a 62 GB box
  evict each other on every model swap. The lock protects a single measurement; it does not
  protect a matrix.

Rules that came out of it: diff the exact staged hunks before committing, always run
`git log origin/<branch>..HEAD` after committing and again before pushing, verify the pushed
diffstat matches the size of the change you intended, and when a foreign commit turns up,
coordinate rather than unilaterally rewriting.

### 6. Small mechanical traps that cost real time

Individually trivial, collectively a few days:

- `pgrep -f <pattern>` **matches its own command line**, so
  `until ! pgrep -f foo; do sleep 5; done` never exits. Cost 15 minutes of not noticing a
  finished job, twice. Same class: `pkill -f` matching the compound shell command that
  invoked it.
- **Never patch a file by line number across multiple passes.** Offsets shift and edits land
  in the wrong function.
- **Check a patch's insertion and deletion counts against what the change should look like.**
  A patch extracted before a fix applied cleanly with zero deletions, which was the tell,
  since the fix modified an existing line. It cost a rebuild.
- **Environment assignments produced by shell parameter expansion are not assignments.**
  A construct that expands to `VAR=value` in a command position does not set the variable.
  Use `env` and verify.
- Absolute paths for container bind mounts. A relative one silently creates a named volume,
  and you read a stale file forever.

### 7. It will happily benchmark the build it just compiled

The agent has no intuition for the shader cache, the page cache, or thermal settling, because
none of those are visible in any output it reads. Every one of those confounds had to be
turned into an explicit written rule with a number attached (discard the first run after a
rebuild; the post-model-swap settle is minutes; a d0 delta from a session's first cell is not
reportable). Once written down they were followed reliably. Before being written down they
were rediscovered three times each.

That is the general shape of it: **the agent is excellent at following a rule it has been
given and poor at inferring that a rule is needed.** Writing the rules down, with the
incident that produced each one, is most of what the memory layer is for.

---

## Publishing discipline

The work feeds three destinations with different rules, and conflating them is a real risk.

**Upstream llama.cpp.** As of 2026-07-23 the project allows AI-generated *code*, with the
contributor fully responsible for every line and required to disclose meaningful AI
involvement. It **prohibits**, in strong terms and without exception, AI-written pull request
descriptions, commit messages, issue text, and replies to reviewers. Automated submissions can
get an account banned.

That split is workable and we work to it: the agent produces **evidence only** for anything
going to GitHub. Measurements, before-and-after test output, reproduction commands, bounds
tables, file and line references, and an explicit note that the prose is the human's to write.
Never formatted as something to paste. The code is fine to author, provided the human reviews
it, understands it, and can discuss it with a reviewer unaided.

Before a series goes out it gets audited for things reviewers actually reject on:

- ASCII only in code and comments.
- Comment tone parity with the target repository, which for llama.cpp means brief, one
  occurrence at the setup site, stating a decision rather than a theory, **no measurement
  numbers in code comments**, and no history narration in tests. We derived those rules from a
  maintainer's literal review comments on our own merged pull request rather than guessing.
- Gating parity with the sibling backends: every assumption a shader hardcodes must be gated
  in `supports_op`. Auditing for this once surfaced a real bug class.
- One consistent AI-disclosure trailer on the human's own commits, in whatever form the target
  repository mandates, and none on commits authored by other people.
- A **terminology audit against the target repository**: our internal vocabulary for several
  of these mechanisms has zero occurrences upstream. Using in-house words in a public patch
  makes it read as coming from somewhere else. We now grep the target for each term and
  substitute the one already in use.
- A **scope audit**: every performance claim names the part it was measured on. "Strided loads
  are slow on AMD" became "gated to AMD, where the strided-load penalty was measured", because
  we measured one APU and one NVIDIA card. This one was caught by the human, not the agent,
  and it is the correction the agent is least likely to make on its own, because an
  over-general claim reads as *more* useful rather than less true.

**The fork and toolbox.** Looser, but this is where a shipped, measured, verified win turned
out to be a specification violation and a 2.4-3.1x regression for everyone on a stock driver.
The lesson generalises past that bug: **the configuration you never test is the one your users
have.** Our development driver was the thing making the violation survivable.
Corollary practice: enumerate and smoke-test the commits that ride along with a release, per
risk surface, before cutting it. A release cut from a branch tip shipped a livelock that way.

**Documents like this one.** The rule here is the artifact-grep rule above, plus the do-not-claim
lists, plus a preference for stating what a result does not support.

---

## What it costs, and what it does not do

It is slow at the start. The harness, the memory scheme and the rules are all overhead before
they are leverage, and for the first month they look like bureaucracy. The point at which it
paid for itself was identifiable: the first time a result contradicted a six-week-old finding
and the old raw artifact settled it in ten minutes instead of being re-run.

It does not replace judgement about what to investigate. Every choice of what to measure next
in EXPLORING.md was a human one. The agent is very good at "here are nine things that could
explain this, here is the cheapest one to eliminate first" and it is not good at "this whole
line of enquiry is worth less than the other thing".

It does not make you right. Part IV of EXPLORING.md is twelve public retractions from four
months. What the system does is make being wrong **cheap and fast** rather than permanent: the
median time from a wrong causal claim to its falsification, in that list, is under a day, and
that is the only metric here worth optimising.

And it needs a human who will read the raw output. Every single retraction in that list was
caught by someone going back to an artifact, or by a downstream user, or by a reader who
noticed prose that sounded machine-written. None of them were caught by the agent
re-examining its own conclusion unprompted.

---

## If you want to copy the useful parts

In rough order of value per unit of effort:

1. **The three-artifact rule.** One script, three files, one index row. An afternoon to build.
   It is the foundation everything else sits on.
2. **The do-not-claim list at the end of every finding.** Free, and it is the thing that stops
   over-claiming at the moment of writing rather than at the moment of review.
3. **One fact per file, edited in place, with its own correction history.** The corrections are
   the asset, not the conclusions.
4. **A "how to apply" line on every finding.** A finding without an action is not retrievable
   when you need it.
5. **The artifact-grep rule.** Before writing "we do X", grep for what X would have left behind.
6. **A hard rule per confound, with the incident and the number attached.** Discard the first
   run after a rebuild. Three launches per arm. Counterbalance A-B-B-A. Compiles are
   benchmarks. Each one of these was rediscovered several times before it was written down, and
   followed reliably afterwards.
7. **Publish the negatives.** They are most of the value, they are what stops the next person
   building the wrong thing, and they are the only part of a research record that ages well.
