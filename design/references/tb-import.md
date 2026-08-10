# Reading the TB

Two accepted inputs. Nothing else.

## 1. A TB document

A file path, or the brief pasted straight into the prompt. Read it as-is.

## 2. A Confluence TB link

A URL. Fetch it with the Atlassian tools (`getConfluencePage`, or `fetch` with the page id).
If the fetch fails, say so and ask for the text instead — don't guess at the contents from the title.

## What not to do

- **Don't search Jira.** A ticket key is not a TB.
- **Don't glob the filesystem** looking for something brief-shaped.
- **Don't reconstruct the TB by interrogating the user.** If they wanted to write it here they
  wouldn't be pointing you at one.

If you have neither input, stop:

> "I need a task brief to design from. Give me the TB document, or paste a Confluence link to it."

## What to pull out

Four things, and only four. Write them into `brief.md` as a short summary.

| What | Why it matters downstream |
|---|---|
| **Problem** | keeps the explorations aimed at something real |
| **Who it's for** | decides density, hand-holding, how much jargon is acceptable |
| **Use cases** | **the important one** — these become the states every exploration must handle |
| **Out of scope** | stops explorations sprawling past what was agreed |

The use cases do the most work. If the TB lists "filter by tag" and "clear all filters", then every
exploration needs an unfiltered state, a filtered state, and a way back. That's what stops
`/design` producing one happy-path screen and calling it done.

## Don't re-ask

Anything the TB answers is settled. Re-asking is the fastest way to make this skill annoying, and it
produces no new information.

If exactly one thing is genuinely missing and it changes the design, ask that single question. Don't
run a questionnaire.
