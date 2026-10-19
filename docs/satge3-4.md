# Agentic RAG Curator: Stages 3–4 Learnings, Mistakes and Fixes

Oct 17, 2026 · @Pranay Gupta

Hybrid search (Stage 3) and RAG generation (Stage 4) now work end to end. Almost every failure came from context quality, model choice or stale deployment state, not from the core algorithms.

## What was built

| Component | File | Key decision |
| --- | --- | --- |
| Text chunker | chunker | Two-stage split: markdown headers first (keeps section title), then 1000-character chunks with 150 overlap |
| Jina embeddings client | jina\_client | Asymmetric modes: retrieval.passage for indexing, retrieval.query for questions; 429 retry with backoff |
| Chunk index | paper\_chunks | knn\_vector, 1024 dimensions, HNSW, cosine similarity; ids are arxiv\_id plus chunk index so re-indexing is idempotent |
| Reciprocal Rank Fusion | rrf.py | Written by hand: score is 1/(k+rank) summed across lists, so consistent ranking beats one lucky top spot |
| Hybrid search | hybrid.py | BM25 and vector search fused with RRF; ids de-duplicated because one paper has many chunks |
| Hybrid evaluation | 15-query eval | Hybrid beat both single methods on precision at 5 (0.333 vs 0.320 and 0.307) |
| LLM client | llm/client.py | OpenAI-compatible request shape, so Gemini, Groq or Ollama is a config change; retries on 429 and 5xx |
| Grounded prompt | llm/prompts.py | Answer only from numbered context blocks; refuse with a fixed sentence when nothing is relevant |
| RAG service | rag.py | Retrieve, build prompt, generate, then map numbered citations back to papers |
| Endpoints | routers/ask.py | POST /ask for a full answer and POST /ask/stream for Server-Sent Events |

## Stage 3 mistakes and fixes

| Problem | Root cause | Fix |
| --- | --- | --- |
| Precision at k looked wrong in the evaluation | The harness divided by the number of results returned instead of by k | Divide by k; found because the numbers did not match a hand calculation |
| Embedding calls failed with rate limits | Jina free tier returns 429 under bursts | Retry up to 5 times with doubling waits (1, 2, 4, 8, 16 seconds) |
| Risk of spending the embedding quota twice | Backfilling all papers before the pipeline was verified | Deferred the full backfill until hybrid search was evaluated on 3 papers |
| One paper could win by repeating in a list | The chunk index returns many chunks per paper, each counted as a rank | De-duplicate ids per list, keeping the best-ranked occurrence, before fusion |
| Vector-only hits showed a null title | Titles were taken from BM25 results only | Known and still open: fetch titles from the papers index, as retrieve\_context already does |

## Stage 4 mistakes and fixes

| Problem | Root cause | Fix |
| --- | --- | --- |
| Ollama Docker image took hours to pull (3.8 GB, restarted after a shutdown) | Slow connection plus a very large image | Moved to a hosted API behind an OpenAI-compatible config, so the provider is three settings |
| compose.yml refused the ollama block | Services landed at the wrong level, likely hidden whitespace | Retype the block by hand and validate with docker compose config before starting |
| Gemini returned 404 for gemini-2.5-flash though it was in the model list | The model was not usable on this key | Tested names in a loop and used gemini-flash-latest; printed the real error body, because PowerShell hides it |
| /ask returned 404 after adding the route | Code is baked into the Docker image, so the running container had old code | Rebuild with docker compose up -d --build app |
| /ask returned 500 days later | OpenSearch container was down; the traceback showed Connection refused | Start OpenSearch and wait for it; not a code bug |
| Gemini returned 503 high demand | Provider overload, not our request | Retry with backoff, plus a Groq fallback model |
| RAFT question answered that details were not in the papers | retrieve\_context sent only the best chunk, which was a passing mention, and never the abstract | Send the abstract plus the best excerpt for every paper |
| Answer invented an acronym expansion and a wrong citation | The fallback model (a small 7B model) ignored the grounding rule | Switched the fallback to a larger Groq model; logged which provider answers |
| Citation read \[2609.2076\] instead of \[2609.20754v1\], so source filtering failed | Models garble long identifiers | Number context blocks \[1\], \[2\] and map the numbers back to papers on the server |
| Model refused, then answered anyway ('not mentioned. However...') | Prompt allowed a soft refusal, then over-strict wording caused wrong refusals | Rule is now: answer from relevant context even if partial; refuse with one fixed sentence only if nothing is relevant |
| Refusals still listed 5 unrelated sources | Fallback to all sources when no citation was found | Return no sources when the answer is the refusal sentence |

## Interview talking points

1. **Hybrid beats either method alone.** BM25 catches exact terms like an acronym, vectors catch paraphrases, and RRF rewards papers ranked well by both. Measured on 15 queries, not assumed.
2. **Rank fusion needs ids, not scores.** BM25 and cosine scores are on different scales, so RRF uses only rank positions. One paper repeating in a list had to be de-duplicated first.
3. **A provider-agnostic LLM client.** One OpenAI-compatible request shape and three settings (base URL, key, model) let the same code run Gemini, Groq or a local Ollama. This is what made the switch away from Ollama a config change.
4. **Grounding is a prompt plus a retrieval problem.** A strict prompt without good context produced refusals; a loose one produced invented answers. Fixing the context (abstract plus excerpt) and tuning the refusal rule together is what worked.
5. **Models mistype long identifiers.** Citing \[1\] and mapping to the paper on the server is more reliable than asking the model to copy 2609.20754v1.
6. **A weak fallback model is worse than an error.** A silent fallback to a small model produced confident wrong answers. Fallbacks need a capability floor and logging of which provider answered.
7. **Streaming over Server-Sent Events.** The model's stream is parsed line by line (data: prefix, a DONE marker, missing content fields), then re-emitted as typed events: token, sources, error.
8. **Resumable batch jobs.** The backfill skips papers that already have chunks, so a rate limit or crash costs nothing on re-run.

## Habits that worked

- **Read the traceback before guessing.** The 500 error looked like a code bug; the log showed OpenSearch was simply down.
- **Test one layer at a time.** Calling hybrid-search directly showed retrieval was fine, which moved the search for the RAFT bug to the context and the model.
- **Check what the running container actually has.** Several failures were old code in a container that had not been rebuilt.
- **Print the real error.** PowerShell hid the response body; catching it showed the provider's message.
- **Look at the raw stream.** Reading the token-by-token output exposed the garbled citation that a finished answer would have hidden.
- **Ask what changed.** The wrong answers began when the fallback model changed, which was only visible once we asked which model was running.
- **Write the fix, then run the opposite test.** After the RAFT fix, the France question confirmed refusals still worked.

## Open items

- [ ] Fix null titles for vector-only papers in the hybrid-search response.
- [ ] Log which LLM provider answered each request (Langfuse will cover this in Stage 5).
- [ ] Retry the streaming call before the first token, as the non-streaming call already does.
- [ ] Add short, vague queries like "What is RAFT" to the 15-query evaluation set.
- [ ] Stage 5a: Redis cache for /ask answers, keyed on the normalized question, number of papers and category.
- [ ] Stage 5b: Langfuse tracing for retrieval, prompt, model, latency and tokens.
