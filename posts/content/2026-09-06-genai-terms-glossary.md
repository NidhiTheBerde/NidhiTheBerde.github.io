Every few weeks a term shows up in a standup or a job description and everyone nods along like it's obvious. Half the time it is, half the time it isn't. So here's a plain-language pass at twelve terms that come up constantly if you're anywhere near generative AI right now, written the way I'd actually explain them to a friend rather than the glossary version.

## Foundation models

**LLM, or Large Language Model.** This is the umbrella term for the giant models trained on huge amounts of text that power things like ChatGPT and Claude. At their core they're doing one thing: predicting what text comes next given everything that came before. Everything else built on top of them, agents, chat interfaces, coding assistants, is scaffolding around that one core skill.

**Transformers.** This is the architecture underneath basically every LLM in production today. The key idea is a mechanism called attention, which lets the model weigh how relevant every other word in the input is when it's figuring out what a given word means. That's what lets these models handle long, complicated sentences and keep track of things mentioned way earlier in a conversation.

## Getting information in and out

**Prompt engineering.** The practice of writing instructions that actually get a model to do what you want. In my experience the real skill isn't clever wording, it's being specific: give the model the context it actually needs, state the constraints explicitly, and don't assume it can read your mind about the format you want back.

**Context window.** How much text a model can hold onto at once, counted in tokens, not words. Once a conversation or document goes past that limit, older content starts getting dropped or summarized away. This matters a lot in practice because a bigger context window means you can feed a model more source material before it starts forgetting the beginning of what you gave it.

**Tokens.** The actual chunks a model reads and writes in, usually pieces of words rather than whole words. This is also the unit everything gets billed and rate-limited in, so token count ends up being the thing you actually optimize for when you're trying to control cost or latency in a pipeline.

## Making a model better at your specific job

**Fine-tuning.** Taking a general-purpose model and training it further on a narrower dataset so it gets noticeably better at one particular kind of task. It's a heavier lift than prompting, since it requires actual training data and compute, but it can bake in behavior that's hard to reliably get through prompting alone.

**RAG, Retrieval Augmented Generation.** Instead of relying only on what a model memorized during training, you look up relevant information from an external source first, then hand that to the model alongside the question. This is how you get a model to answer accurately about something that happened after its training cutoff, or about your own private data it was never trained on in the first place.

**Zero-shot learning.** A model handling a task correctly without ever being shown an example of that exact task. This is honestly one of the more surprising things about large models: their general training turns out to generalize well enough that they can often do something reasonable on a task they've never explicitly seen.

## The knobs and the failure modes

**Embeddings.** A way of turning words, sentences, or whole documents into a list of numbers such that things with similar meaning end up close together mathematically. This is the whole trick behind semantic search and RAG: instead of matching keywords, you're matching meaning.

**Temperature.** A setting that controls how much randomness goes into a model's output. Low temperature makes the model pick the most likely next word almost every time, which is what you want for anything that needs to be consistent and repeatable. Higher temperature lets it take more chances, which is better for brainstorming or creative writing where you actually want variety.

**Chain-of-thought.** Asking a model to reason through a problem step by step instead of jumping straight to a final answer. It sounds like a small prompting trick, but it genuinely improves accuracy on anything that requires multi-step reasoning, and it has the nice side effect of giving you a trail to check when the final answer looks wrong.

**Hallucination.** When a model states something false with the same confidence it uses for something true. It doesn't know the difference between the two from the inside, it's just producing plausible-sounding text, and that's exactly what makes this hard to catch without independently checking the claim.

A few of these stopped being abstract definitions for me pretty fast. Getting embeddings and retrieval to actually behave, keeping temperature low enough that structured output stays reliable, catching a model confidently stating something it never actually verified: that's most of what debugging an AI pipeline turns out to be in practice.
