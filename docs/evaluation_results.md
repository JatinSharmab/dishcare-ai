# Evaluation results

## Offline golden replay

Run `python -m evaluations.runner --require-pass`. The recorded v1 run passed 9/9 cases. The real graph, validators and SQLite seed data ran with deterministic model and retrieval fixtures.

| Check | Passed |
| --- | ---: |
| Intent classification | 9/9 |
| Language | 9/9 |
| Expected tool selection | 9/9 |
| Exact proposed tool arguments | 4/4 |
| Expected facts | 9/9 |
| Source present in returned citations | 3/3 |
| Answer keywords | 9/9 |
| Composite task success | 9/9 |

The offline latency ranged from 0.12 to 68.02 ms on this Windows run. It excludes network inference. `python -m evaluations.prompt_comparison --simulate-regression` deliberately routed the Hindi balance case incorrectly. It detected the drop from 9/9 to 8/9 in intent, tool selection, verified facts and task success, and exited with code 1.

## Live-model sample

Run `python -m evaluations.runner --live --judge --case balance-en --case balance-hi --case technical`. The three cases passed the task checks with seeded account data and fixture retrieval. The configured Gemini/Groq fallback handled three Gemini HTTP 503 responses. The judge marked 3/3 answers relevant and faithful, and flagged 0/3 for unsupported claims. Wall times for the graph were 15.76 s, 5.95 s, and 2.87 s. The graph timing excludes judge calls. These results describe a small run using fallback and controlled retrieval.

## Review methodology

An offline tool argument check uses exact equality, including case and formatting. Answer keyword checks catch obvious regressions and human review should assess naturalness and whether a technically correct answer resolves the issue. A model judge can miss unsupported claims and can reproduce provider bias. Collect human labels for relevance, factual accuracy, and resolution, adjudicate disagreements, and compare the judge against those labels.

For microphone or recorded WAV tests, score raw utterances with `python -m evaluations.voice_eval models/voice-manifest.json`. Report WER by language and noise condition, and time end-of-utterance to first audio separately from ASR, graph, and synthesis. The WebSocket returns durations for ASR, graph, synthesis, and total processing. End-to-end timing also includes endpointing, transit and device playback.

## Local speech sample

Ran `python -m evaluations.voice_eval --synthetic` with Faster Whisper base INT8 on CPU, separate Piper voices, and Silero ONNX. The two inputs were synthesized locally. Raw WER case-folds the text and retains punctuation.

| Clip | Words | WER | ASR | Piper synthesis | Speech frames |
| --- | ---: | ---: | ---: | ---: | ---: |
| English balance question | 5 | 0% | 1,727 ms | 189 ms | 40 |
| Hindi balance question | 4 | 50% | 1,891 ms | 171 ms | 43 |

Corpus WER was 22.22% across nine words. In an earlier Hindi run, Whisper produced an Urdu-script transcript; the Hindi prompt encouraged Devanagari, but the later transcript still misspelled the word for balance and differed in punctuation. These samples exclude live microphone noise, LLM and network latency.

The live prompt comparison `python -m evaluations.prompt_comparison --live --case balance-hi` recorded 1/1 passing for both v1 and v2 on the Hindi balance question. This single case does not establish a general improvement.
