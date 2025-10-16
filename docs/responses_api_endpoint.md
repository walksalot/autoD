
# OpenAI Responses API: Comprehensive Developer Guide (OCtober 2025)

## 1 Overview – why the Responses API matters

OpenAI’s **Responses API** is the successor to the Chat Completions API.  It combines the simplicity of chat completion with the tool‑calling and agentic capabilities of the deprecated Assistants API.  According to OpenAI, the Responses API is now the recommended interface for all new projects; Chat Completions remains supported but should be considered legacy.

### Key motivations

* **Agentic loop** – The API automatically orchestrates multiple tool calls (web search, file search, computer use, code interpreter, remote MCP, image generation and your own functions) in a single request.  This agentic loop preserves internal reasoning state between turns and gives the model the chance to think before it answers.
* **Built‑in multi‑turn state** – State can be stored automatically when `store=true` or by passing a `previous_response_id`.  Conversations become **stateful**, so you no longer have to manually append messages like in Chat Completions.  Encrypted reasoning tokens allow you to keep a stateless flow (for privacy) while still benefiting from reasoning.
* **Lower costs** – The caching mechanism, together with support for long context windows, significantly reduces token costs (OpenAI reports 40–80 % savings compared with Chat Completions).  Cached input tokens are billed at ~10 % of the normal input price.
* **Future proof** – New models (GPT‑5 series, O‑series, GPT‑4.1, etc.) and features (reasoning tokens, tool calling) are only available through the Responses API.  The Assistants API has a sunset date of 26 Aug 2026, so migrating to Responses is essential.

### How it differs from Chat Completions

| Capability | Chat Completions | Responses API |
| --- | --- | --- |
| Text generation | ✔︎ | ✔︎ |
| Vision (image inputs) | ✔︎ | ✔︎ |
| Structured outputs | ✔︎ | ✔︎ (uses `text.format`) |
| Function calling | ✔︎ | ✔︎ (strict by default) |
| Web search | ❌ | ✔︎ |
| File search | ❌ | ✔︎ |
| Computer use | ❌ | ✔︎ |
| Code interpreter | ❌ | ✔︎ |
| MCP (remote self‑hosted compute) | ❌ | ✔︎ |
| Image generation | ❌ | ✔︎ |
| Reasoning summaries | ❌ | ✔︎ |
| Audio input & output | ✔︎ | **Coming soon** |

Chat Completions returns a `choices` array containing messages; the Responses API returns an array of **Items** – each Item is either a message, a tool call, a tool call result, a reasoning item or other internal output.  Multiple generations (`n` parameter) are not supported in Responses; only one generation is returned.

## 2 Migrating from Chat Completions

The Responses API is a superset of Chat Completions, so most message‑generation code can be ported by updating endpoints.  OpenAI’s migration guide recommends the following steps:

1. **Change endpoint** – Replace calls to `POST /v1/chat/completions` with `POST /v1/responses`.  Simple prompts (without functions or multimodal inputs) are immediately compatible.
2. **Update item definitions** – Chat Completions uses arrays of messages (`[{role, content}, …]`), while Responses uses an `input` field that can be a string or a list of Item objects.  An Item may be a `message`, `function_call`, `function_call_result`, `tool_call`, `tool_result` or `reasoning`.  For simple prompts, you can still pass a single string as `input`.
3. **Multi‑turn conversations** – In Chat Completions you must manage context manually by concatenating messages.  In Responses, you can either pass `previous_response_id` to chain context or set `store=true` so the API stores context for you.  For privacy, you can use **encrypted reasoning** to persist reasoning tokens without storing intermediate state.
4. **Function definitions** – In Chat Completions functions are defined using externally tagged polymorphism.  In Responses they are internally tagged and **strict by default**, meaning the schema is enforced.  Use the `tools` array to define functions along with built‑in tools.
5. **Structured outputs** – In Chat Completions you specify `response_format`; in Responses, structured outputs are requested via `text.format` in the `instructions` or by specifying a `schema` when using Structured Outputs.
6. **Native tools** – With Chat Completions you must implement your own tools (e.g., a fetch call for web search).  The Responses API provides built‑in tools such as `web_search`, `file_search`, `computer_use` and `code_interpreter` so you no longer need to embed fetch code.
7. **Incremental migration** – Because Chat Completions will remain supported, you can move user flows that need advanced reasoning or tool use to Responses while keeping simple flows on Chat Completions.

### Changes to functions and tool calls

In the Responses API a tool call and its result are two distinct Item types linked by a `call_id`.  The `tools` array defines functions and built‑in tools that the model is allowed to use.  Each function must include a `name`, a `description` and a **JSON schema** describing `parameters`.  In contrast to Chat Completions, functions are strict by default; unknown parameters will result in an error.  When the model decides to call your function, it will return an Item of type `function_call` containing the arguments; you should execute the function, then send its output back as a `function_call_result` Item (with the same `call_id`).

### Why you should stop using Chat Completions

OpenAI recommends using Responses for all new projects because it offers better performance, improved reasoning, lower costs, built‑in tools, and stateful context.  It is future‑proof: new models like GPT‑5 Pro and O‑series Pro are only available through Responses.  The Assistants API is being retired on **26 Aug 2026**, so migrating early reduces maintenance overhead.

## 3 Endpoint and request structure

### Endpoint

* **Create a response** – `POST /v1/responses`
* **Retrieve a response** – `GET /v1/responses/{id}`
* **Delete a response** – `DELETE /v1/responses/{id}`
* **Stream a response** – `POST /v1/responses (stream=true)`
* **Cancel or poll background jobs** – `POST /v1/responses (background=true)` followed by `GET /v1/responses/{id}` to poll or `DELETE /v1/responses/{id}` to cancel [oai_citation:0‡learn.microsoft.com](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/responses#:~:text=Background%20tasks).

### Request body

A typical request contains the following fields (only the most common are shown here; see the API docs for full definitions):

| Field | Type | Description |
| --- | --- | --- |
| `model` | string | Model name (e.g., `gpt-5`, `gpt-5-pro`, `gpt-4o-mini`, `o3` etc.).  Models vary in reasoning ability, speed and cost (see Section 6). |
| `input` | string or array of Item objects | User input.  A string is treated as a single message with role “user”.  An array allows interleaving messages (`type="message"`, with `role` & `content`), image inputs (`type="input_image"`), function call results (`type="function_call_result"`), tool call results (`type="tool_result"`) or reasoning items. |
| `instructions` | string | System prompt.  Think of this as the “persona” or high‑level instructions for the model [oai_citation:1‡datacamp.com](https://www.datacamp.com/tutorial/openai-responses-api#:~:text=This%20example%20demonstrates%20key%20patterns,when%20using%20the%20Responses%20API). |
| `temperature` | number (0–2) | Controls randomness.  Low values give deterministic, conservative responses; higher values produce more variation [oai_citation:2‡datacamp.com](https://www.datacamp.com/tutorial/openai-responses-api#:~:text=This%20example%20demonstrates%20key%20patterns,when%20using%20the%20Responses%20API). |
| `top_p` | number (0–1) | Controls nucleus sampling; lower values restrict to more probable tokens.  Use either `temperature` or `top_p` but not both. |
| `max_output_tokens` | integer | Hard limit on output tokens (defaults vary by model).  Setting this prevents runaway responses. |
| `tool_choice` | string or object | `"auto"` (default) lets the model decide whether and which tools to call; `"none"` disables tools; or specify a particular tool’s name to force its use. |
| `tools` | array | List of built‑in tools and custom functions the model may call.  Each tool must specify a `type` and additional configuration (see Section 5). |
| `previous_response_id` | string | ID of a prior response to continue the conversation.  When using this, you must also send the new `input` and optional `instructions`. |
| `store` | boolean | If true, the API stores conversation state (default true).  Set to false if you do not want OpenAI to retain context; in that case you must pass back `encrypted_content` to resume reasoning. |
| `reasoning` | object | Controls the model’s reasoning effort and how much of its chain of thought you get back.  For example, `{ "effort": "auto", "summary": "low" }` (options `minimal`, `low`, `medium`, `high`).  Higher effort uses more compute. |
| `include` | array | When using stateless mode (`store=false`), specify which encrypted items to include in the next call (`"reasoning"`, `"tools"`, etc.) [oai_citation:3‡learn.microsoft.com](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/responses#:~:text=Encrypted%20Reasoning%20Items). |
| `stream` | boolean | If true, the API streams events as they occur (see streaming below).  Each event includes either partial message deltas, tool calls, tool results or reasoning summaries [oai_citation:4‡datacamp.com](https://www.datacamp.com/tutorial/openai-responses-api#:~:text=Implementing%20streaming%20for%20responsive%20applications). |
| `background` | boolean | Runs the response as an asynchronous job.  Useful for long tool‑calls (e.g.[... ELLIPSIZATION ...]n appropriate, and you must return its result as a `function_call_result` Item.  Functions are strict by default in Responses; unknown parameters will cause validation errors.

### Tool usage patterns

1. **Define the tools** – In the request, include a `tools` array with built‑in tools or function definitions.  Each built‑in tool has its own configuration (e.g., `code_interpreter` needs no parameters; `web_search` may accept `search_config`; `file_search` requires a list of file IDs).
2. **Enable tool calling** – Leave `tool_choice` unset or set it to `"auto"` so the model may choose to call tools.  To disable tool calls, set `tool_choice="none"`.  To force a specific tool call, specify the tool’s `name` in `tool_choice`.
3. **Handle tool calls** – When a tool call occurs, the streaming API will emit a `tool_call` Item with `name` and `arguments`.  For built‑in tools, the API automatically executes the tool and sends a `tool_result` Item.  For custom functions you must intercept the `function_call`, run your code, then send the result back via a new API call with `previous_response_id` and a `function_call_result` Item containing the `call_id` and the JSON result.  The model will continue the conversation with this result [oai_citation:5‡datacamp.com](https://www.datacamp.com/tutorial/openai-responses-api#:~:text=our%20next%20section).

## 5 Multimodal input and files

### Text and images

The `input` field can include images.  To send an image you can either:

1. Provide an `input_image` Item with `{"type": "input_image", "image": {"url": "https://..."}}`, or
2. Embed a base64‑encoded image with `{"type": "input_image", "image": {"data": "<base64>"}}` [oai_citation:6‡datacamp.com](https://www.datacamp.com/tutorial/openai-responses-api#:~:text=,applications).

Each image counts as a certain number of tokens depending on resolution (e.g., ~85 tokens for low‑detail images or up to ~1 100 tokens for high‑detail images [oai_citation:7‡blog.laozhang.ai](https://blog.laozhang.ai/ai/openai-gpt-4o-api-pricing-guide/#:~:text=Audio%20Input%20%2440,detail%3A%2085%20tokens%20per%20image)).  You can mix text and images in the `input` array; the model will receive them in order.  The maximum number of images per request may vary by model.

### File inputs

You can upload PDFs, Word, Markdown or spreadsheets to OpenAI storage and reference them in the `file_search` tool.  When using file search, specify the file IDs (or search scope) in the tool configuration.  Files remain stored and billed per gigabyte per day (first GB free) [oai_citation:8‡the-rogue-marketing.github.io](https://the-rogue-marketing.github.io/openai-api-pricing-comparison-october-2025/#:~:text=,Responses%20API%20only).

### Audio and speech

As of October 2025, audio input/output is still “coming soon” for the Responses API.  For speech synthesis or transcription, continue to use separate APIs (e.g., TTS or Whisper) until the Responses API adds native support.

## 6 Models available via Responses API (October 2025)

The following tables list models available via the Responses API along with their base **Batch** pricing (per million tokens) and key attributes.  Token prices decrease significantly when using **cached input tokens** (≈90 % discount).  More expensive tiers (Priority) and cheaper tiers (Batch, Flex) exist but are not covered here.

### GPT‑5 family

| Model | Reasoning & speed | Context window / max output | Knowledge cutoff | Pricing (input / cached input / output)* | Notes |
|---|---|---|---|---|---|
| **GPT‑5 Pro** | Highest reasoning, slowest speed | 400 K / 272 K tokens | Sep 30 2024 | $15.00 / (N/A, no cached input) / $120.00 | Available only via Responses; uses extra compute to deliver more precise answers and defaults to `reasoning.effort: high`; does not support code interpreter. |
| **GPT‑5** (flagship) | Higher reasoning, medium speed | 400 K / 128 K | Sep 30 2024 | $1.25 / $0.125 / $10.00 | Best model for coding, reasoning and agentic tasks across domains.  Supports vision and all built‑in tools. |
| **GPT‑5 Mini** | High reasoning, fast | 400 K / 128 K | May 31 2024 | $0.25 / $0.025 / $2.00 | Cost‑efficient version of GPT‑5 for well‑defined tasks. |
| **GPT‑5 Nano** | Average reasoning, very fast | 400 K / 128 K | May 31 2024 | $0.05 / $0.005 / $0.40 | Best for summarization and classification; cheapest GPT‑5 model. |
| **GPT‑5 Codex** | Higher reasoning, medium speed | 400 K / 128 K | Sep 30 2024 | $1.25 / $0.125 / $10.00 | Optimized for agentic coding tasks; only available via Responses and updated regularly. |

\*Pricing shown is per million tokens for the **Batch** tier.  “Cached input” refers to reused prompt tokens – when the same tokens appear again in the system or instructions, they are billed at the cached input rate (≈10 % of the normal rate).  Output prices apply to tokens generated by the model.

### O‑series (reasoning models preceding GPT‑5)

| Model | Reasoning & speed | Context window / max output | Knowledge cutoff | Pricing (input / cached / output) | Notes |
|---|---|---|---|---|---|
| **o3** | Highest reasoning, slowest | 200 K / 100 K | Jun 1 2024 | $2.00 / $0.50 / $8.00 | Well‑rounded reasoning model for math, science, coding and visual reasoning tasks; succeeded by GPT‑5. |
| **o3‑mini** | Higher reasoning, medium speed | 200 K / 100 K | Oct 1 2023 | $1.10 / $0.55 / $4.40 | New small reasoning model delivering high intelligence at lower cost. |
| **o3‑pro** | Highest reasoning, slowest | 200 K / 100 K | Jun 1 2024 | $20.00 / (no cached input) / $80.00 | Version of o3 with more compute for tougher reasoning; available only via Responses and defaults to background mode. |

### GPT‑4.1 family (non‑reasoning models with huge context)

| Model | Intelligence & speed | Context window / max output | Knowledge cutoff | Pricing (input / cached / output) | Notes |
|---|---|---|---|---|---|
| **GPT‑4.1** | Higher intelligence, medium speed | 1 M tokens / 32 768 tokens | Jun 1 2024 | $2.00 / $0.50 / $8.00 | Smartest non‑reasoning model; excels at instruction following and tool calling. |
| **GPT‑4.1 Mini** | High intelligence, fast | 1 M / 32 768 | Jun 1 2024 | $0.40 / $0.10 / $1.60 | Smaller, faster version of GPT‑4.1. |
| **GPT‑4.1 Nano** | Average intelligence, very fast | 1 M / 32 768 | Jun 1 2024 | $0.10 / $0.025 / $0.40 | Cheapest GPT‑4.1 model; good for simple instruction following. |

### GPT‑4o family (omni models)

| Model | Intelligence & speed | Context / max output | Knowledge cutoff | Pricing (input / cached / output) | Notes |
|---|---|---|---|---|---|
| **GPT‑4o** | High intelligence, medium speed | 128 K / 16 384 | Oct 1 2023 | $2.50 / $1.25 / $10.00 | Versatile, accepts text and image inputs; best general model outside reasoning models. |
| **GPT‑4o Mini** | Average intelligence, fast | 128 K / 16 384 | Oct 1 2023 | $0.15 / $0.075 / $0.60 | Fast, affordable small model for focused tasks. |

## 7 Pricing for built‑in tools and special APIs

* **Code interpreter** – $0.03 per session (runtime charges may apply) [oai_citation:9‡the-rogue-marketing.github.io](https://the-rogue-marketing.github.io/openai-api-pricing-comparison-october-2025/#:~:text=,Responses%20API%20only).
* **File search storage** – $0.10 per GB per day (first GB free) [oai_citation:10‡the-rogue-marketing.github.io](https://the-rogue-marketing.github.io/openai-api-pricing-comparison-october-2025/#:~:text=,Responses%20API%20only).
* **File search tool calls** – $2.50 per 1 k calls (Responses API only) [oai_citation:11‡the-rogue-marketing.github.io](https://the-rogue-marketing.github.io/openai-api-pricing-comparison-october-2025/#:~:text=,Responses%20API%20only).
* **Web search preview** – $25 per 1 k calls for `gpt‑4o` and `gpt‑4.i` (not yet in our tables) mini models; $10 per 1 k calls for GPT‑5 and O‑series [oai_citation:12‡the-rogue-marketing.github.io](https://the-rogue-marketing.github.io/openai-api-pricing-comparison-october-2025/#:~:text=Web%20Search%20Pricing).
* **Image generation** – Approximately $0.01 (low quality), $0.04 (medium) or $0.17 (high) per image [oai_citation:13‡the-rogue-marketing.github.io](https://the-rogue-marketing.github.io/openai-api-pricing-comparison-october-2025/#:~:text=Image%20Generation%20API).

The Batch API can lower input/output costs by ~50 % for asynchronous jobs, while Priority tier (not shown) trades higher cost for faster latency [oai_citation:14‡the-rogue-marketing.github.io](https://the-rogue-marketing.github.io/openai-api-pricing-comparison-october-2025/#:~:text=%2A%20Batch%20API%3A%20Save%2050,go).

## 8 Best practices

* **Choose the right model** – For complex reasoning, use GPT‑5 Pro or o3‑pro; for general tasks use GPT‑5 or GPT‑4o; for classification or summarization use mini/nano variants.  Non‑reasoning models (GPT‑4.1 family) deliver huge context but no chain‑of‑thought; they are ideal for pattern matching or retrieval augmentation.
* **Use system `instructions` wisely** – Provide clear, concise system prompts; avoid repeating them every turn by enabling `store` or using caching.  Cached input tokens are billed at 10 % of the normal rate.
* **Control response length** – Always set `max_output_tokens` to avoid unexpectedly large bills.  Reasoning models can produce long explanations; limit them where appropriate.
* **Leverage tools when beneficial** – Use `web_search` for fresh data, `file_search` for retrieval‑augmented generation, `computer_use` for tasks that require web interaction, and `code_interpreter` for heavy data processing.
* **Handle streaming** – For real‑time experiences, enable `stream=true` and process events incrementally.  Streaming cannot be combined with `background` or `store=true` [oai_citation:15‡learn.microsoft.com](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/responses#:~:text=Background%20tasks).
* **Ensure privacy** – When dealing with sensitive data, set `store=false` and rely on encrypted reasoning tokens.
* **Avoid Chat Completions** – Unless maintaining legacy flows, always use the Responses API.  It is the future‑proof path for new models and features.

## 9 Summary

The Responses API unifies conversation, tool use and advanced reasoning into a single, stateful endpoint.  It supersedes Chat Completions by adding multi‑turn context management, built‑in tools, improved cost efficiency and support for the latest models.  Migrating involves updating endpoints and adopting Items instead of messages, but the benefits – better reasoning, lower costs and future compatibility – outweigh the effort.  Adhering to the guidelines above will help you build robust, agentic applications with OpenAI’s most capable models.


Using the OpenAI Responses API (Migrating from Chat Completions)

Introduction to the Responses API

The Responses API is OpenAI’s new unified endpoint for interacting with language models, introduced in early 2025 ￼. It combines the simplicity of the older Chat Completions API with powerful new capabilities such as built-in tool usage and multimodal support ￼ ￼. In other words, the Responses API is a superset of the Chat Completions API – anything you could do with Chat Completions, you can also do with Responses, plus more ￼. OpenAI has positioned the Responses API as the future of their platform for building AI applications, especially agent-like systems that perform complex or multi-step tasks ￼ ￼.

Why a new API? The Responses API was created to simplify building “agentic” applications – AI systems that can use tools and perform multi-step reasoning to accomplish tasks on behalf of users ￼ ￼. Developers found it challenging to orchestrate complex prompts and multi-call workflows with the old APIs, so OpenAI’s Responses API introduces a more flexible, all-in-one format ￼ ￼. It allows a single API call to handle multi-turn conversations, function (tool) calls, and even web or file searches within the model’s response cycle ￼ ￼. This greatly streamlines development of chatbots, coding assistants, and other AI agents.

Importantly, our projects will exclusively use the Responses API endpoint (OpenAI REST path POST /v1/responses) rather than the older chat completions endpoints. OpenAI itself recommends that for any new integration, developers start with the Responses API, since it encompasses all chat functionality and is actively being improved with new features ￼. (Chat Completions is still supported for backward compatibility and simple use cases not needing tools, but it is no longer the preferred interface ￼.) By standardizing on the Responses API, we ensure we can leverage the latest models and capabilities and avoid any deprecated patterns.

Key Features and Improvements

The Responses API offers many features beyond what the old Chat Completions provided:
	•	Unified Chat and Tools: You can get the model’s chat response and invoke tools in one call. The model can decide to call a built-in tool (like web search or file lookup) or a developer-defined function as part of responding ￼ ￼. This means the model can gather information or take actions mid-response, then continue and produce a final answer – all handled seamlessly by the API. In the Chat Completions API, such behavior required external orchestration or multi-step function calling; now it’s integrated.
	•	Built-in Tools: Out of the box, certain powerful tools are provided:
	•	Web Search – the model can perform web searches to fetch up-to-date information with cited sources ￼.
	•	File Search – the model can search the content of files you’ve uploaded (e.g. documents) to retrieve context ￼.
	•	Computer Use (Code Interpreter) – the model can execute code or interact with a virtual computer environment to perform calculations or other operations ￼.
	•	Function Calling (Custom Tools) – you can enable the model to call your own custom functions (tools) that you define, similar to the function calling feature in Chat Completions ￼. The Responses API generalizes this by treating functions as just another kind of tool the model can use. (In fact, GPT-5 introduced a new Custom Tools feature where the model can output a plaintext command to invoke a tool, not just JSON, giving more flexibility ￼ ￼.)
These tools can be specified in your API request and the model will decide if and when to use them. For example, if you allow the web_search_preview tool, the model may insert a web search step to retrieve live data and then incorporate it into its answer ￼ ￼. All of this happens within the single API call’s workflow.
	•	Multimodal Input/Output: The new API accepts multiple input types in one request – not just text, but also images, and even audio or file inputs ￼ ￼. For example, you can ask a question and provide an image at the same time, and the model (if it’s a vision-capable model) can reason about the image and answer accordingly ￼ ￼. GPT-4o was the first multimodal model (“omni” model) capable of consuming text, images, audio, and video inputs and producing text, image, or audio outputs ￼. Newer models like GPT-4.1 and GPT-5 also handle text+image input (and GPT-4o remains unique in supporting direct audio I/O, see Models below). By using Responses API, we can seamlessly send these different input types in a single request (the input can be an array mixing text and image items, for example) ￼ ￼. This eliminates the need for separate API calls for vision or audio tasks.
	•	Simplified Interface: The request format is more straightforward for basic uses. You no longer have to wrap user prompts in a messages list with roles if you don’t need multiple turns. The Responses API lets you simply pass an input string for a single-turn prompt ￼ ￼. Under the hood, this is equivalent to a single user message. If you do need to include multiple messages or roles (system/developer instructions, multi-turn conversation, etc.), you can pass an array to input or use the instructions field (see Usage below). This flexibility makes simple prompts less verbose while still allowing complex dialogues when needed.
	•	New Developer Role: In addition to the traditional roles (system, user, assistant), the Responses API introduces a developer role for messages ￼. Developer messages are similar to system instructions in that they are provided by the application (not the end-user), but they have a lower priority than the system role. This gives fine-grained control: you can enforce high-level policies or persona with a system message, and use a developer message to give more contextual guidance or modifications without overriding the core system directives. The model treats system role instructions as highest priority, followed by developer, then user messages ￼ ￼. In practice, the developer role is useful for dynamic instructions (like on-the-fly hints, safety guardrails, or chain-of-thought guidance) that you want to inject programmatically, while keeping a stable system policy separate. If there’s a conflict between system and developer instructions, the system message will generally take precedence (ensuring your high-level policies are not violated).
	•	Conversation State Management: The Responses API is designed to handle conversation context more easily, especially in agent scenarios. Each response can be stored on the OpenAI server (by default) and assigned an id. You can reference the previous_response_id in a new request to implicitly include the entire context of that prior exchange ￼. This means you don’t need to resend all prior messages manually to continue a conversation – the API can recall them if you use the previous ID (this is similar to how ChatGPT remembers past turns). For stateless usage (or if you disable storing), you can still pass conversation history in the input array manually. Either way, the API provides a unified conversation memory mechanism. This is part of why it’s called a stateful API ￼. Additionally, the Responses API returns structured data about the conversation and any reasoning the model did (e.g., you can request an encrypted form of the model’s hidden reasoning steps for multi-turn use without storing data ￼). All these tools make it easier to maintain and inspect conversation state compared to the older methods.
	•	Enhanced Streaming and Event Handling: Like Chat Completions, the Responses API supports streaming outputs, but now it streams structured events rather than just text deltas. When stream=True, the API will send a series of events that could include token-by-token text (text.delta events for the assistant’s answer) and events for tool calls or other actions ￼ ￼. The streaming data format is richer, allowing your client code to react to different event types – for instance, you could detect a web_search_call event and log that the model is using the web, or you could stream intermediate reasoning if provided. In practice, handling the stream is slightly more complex than before, but it gives more insight into the model’s process. For simple cases, you can still just read the final text output as it streams in chunks ￼.
	•	Improved Reasoning Capabilities: The new API goes hand-in-hand with new reasoning models (discussed below). Notably, it introduces options to control the model’s reasoning effort and response verbosity, which were not available before. These allow you to trade-off speed and cost versus thoroughness on the fly ￼ ￼. For example, GPT-5 allows a minimal reasoning mode where it spends almost no time in chain-of-thought, producing answers much faster (with fewer “hidden” reasoning tokens) – useful for straightforward queries ￼ ￼. On the other end, you can ask for high effort reasoning on complex tasks so the model thinks through more steps internally before answering (which may improve quality at the cost of latency). Similarly, you can set the desired answer length/detail via a verbosity parameter (low, medium, high) ￼ ￼. This level of control was not present in the Chat Completions API and gives us finer tuning of responses to fit each use case.
	•	Other Usability Improvements: The Responses API also offers:
	•	A unified item-based output design: The API response returns a list of output items representing everything the model did (messages, tool calls, etc.) ￼ ￼. For example, if the model performed a web search and then answered, the output array might contain a web_search_call item with the query, followed by a message item with the assistant’s answer ￼ ￼. This structured output is easier to parse programmatically, and you can include extra fields (like web search sources, function outputs, etc.) via the include parameter if you need detailed logs ￼ ￼. The Python SDK even provides a convenient response.output_text property to directly get the final answer text ￼.
	•	Simpler polymorphism: The API automatically figures out how to handle different input types (text vs image vs file) and output formats without a lot of extra parameters. It uses an "input" field for everything (with type tags internally for non-text) rather than separate endpoints for each modality ￼.
	•	Integrated Observability: Because responses are stored (for 30 days by default) and can be retrieved by ID, OpenAI provides monitoring tools like a trace viewer to inspect agent behavior and debug issues. This is beyond the API itself, but it’s enabled by the Responses infrastructure ￼.
	•	No separate billing: Using the Responses endpoint itself does not incur additional fees beyond the normal usage of models and tools. Tokens and tool calls are billed at the standard rates (see Pricing) ￼. So there’s no cost penalty for choosing Responses API over older endpoints.

In summary, the Responses API is a one-stop interface that simplifies our code (single endpoint for all tasks) while unlocking advanced capabilities. We will not use the older chat/completions or completions endpoints in our projects at all – everything routes through v1/responses to keep our integration consistent and up-to-date with OpenAI’s latest features.

Supported Models and Pricing Overview

OpenAI’s newest and most capable models are available via the Responses API. Here are the key model families we will use, along with their capabilities and pricing:
	•	GPT-5 Series (GPT-5, GPT-5 Mini, GPT-5 Nano, GPT-5 Pro) – Latest Frontier Models. Released August 2025, GPT-5 is currently the flagship model for complex reasoning, coding, and tool-using tasks ￼ ￼. It excels at producing high-quality code, following detailed instructions, and chaining many tool calls reliably for “agentic” tasks ￼ ￼. GPT-5 is effectively state-of-the-art in many benchmarks, especially coding (e.g. ~75% on a difficult code test, significantly better than predecessors) ￼. Uniquely, GPT-5 introduces adjustable reasoning effort and verbosity controls, as mentioned. The GPT-5 family comes in three sizes:
	•	GPT-5 (base) – the largest, most powerful version (sometimes called the “thinking” model in system cards). Best for the hardest problems, complex multi-step reasoning, or heavy coding tasks ￼ ￼. It has broad world knowledge and uses more internal reasoning by default, so it’s slower and costlier for trivial tasks ￼. Price: $1.25 per 1M input tokens, $10 per 1M output tokens ￼ ￼.
	•	GPT-5 Mini – a mid-sized variant offering a balance of power vs cost. It’s faster and much cheaper, while still handling reasoning tasks well ￼ ￼. Good for high-volume or user-facing chat where response time matters but you still need strong capability. Price: $0.25 per 1M input tokens, $2 per 1M output tokens ￼ ￼ (about 5× cheaper than base GPT-5).
	•	GPT-5 Nano – a smaller, high-throughput model optimized for speed and affordability. Ideal for lightweight tasks, quick classifications, or simple Q&A where cost is critical and superhuman reasoning is not required ￼ ￼. It’s the fastest of the GPT-5 series. Price: $0.05 per 1M input tokens, $0.40 per 1M output tokens ￼ ￼ (extremely low cost).
	•	GPT-5 Pro – a special very-high-precision model. This model is the “smartest and most precise” but extremely expensive ￼. It’s less commonly used due to cost, but might be available for niche use cases requiring maximum accuracy. Price: $15 per 1M input tokens, $120 per 1M output tokens ￼ (an order of magnitude above even GPT-4). In most cases, we would not use GPT-5 Pro unless explicitly justified.
All GPT-5 variants support both text and image inputs (multimodal) and text outputs ￼ ￼. GPT-5’s context window is huge – up to 400k tokens (around 300k for prompt + 100k for model’s reasoning) ￼ ￼ – enabling it to handle or produce very large documents (hundreds of thousands of words). One thing to note: GPT-5’s API version is the “reasoning” model (for maximum performance). There is also a gpt-5-chat model (sometimes called GPT-5 Chat or GPT-5 Instant) which is a version tuned for faster responses with less reasoning, used internally in ChatGPT’s UI ￼ ￼. OpenAI makes gpt-5-chat-latest available via API, but they actually recommend using GPT-5 or GPT-4.1 instead in most cases ￼ ￼. For our purposes, we will default to the main GPT-5 (with adjustable effort) or its mini/nano variants, rather than the chat-tuned model, to get better consistency and developer control.
	•	GPT-4.1 Series (GPT-4.1, GPT-4.1 Mini, GPT-4.1 Nano) – High-Performance Non-Reasoning Models. Launched April 2025, GPT-4.1 models were a major upgrade over GPT-4 and GPT-4o, offering improved coding ability, instruction-following, and an extremely large context window ￼ ￼. These models do not engage in extensive hidden reasoning like GPT-5, which makes them slightly more straightforward and sometimes faster for single-step tasks. They are considered the best all-purpose models when advanced reasoning or tool chaining isn’t needed for the task ￼ ￼. GPT-4.1 is multimodal (accepts text and images) and was OpenAI’s first model to support a 1 million token context window ￼ ￼, meaning it can handle entire books or large codebases as input. The family includes:
	•	GPT-4.1 (base) – a very powerful general model (often outperforming the older GPT-4 in every way). It’s great at complex tasks that don’t require chaining many reasoning steps. For example, it’s excellent at understanding lengthy documents, following complex instructions in a single prompt, and even some coding tasks ￼ ￼. It improved coding benchmark performance by ~21% over GPT-4o and has higher reliability in following instructions to the letter ￼ ￼. Price: $2.00 per 1M input tokens, $8.00 per 1M output tokens ￼.
	•	GPT-4.1 Mini – a mid-sized version that retains much of GPT-4.1’s intelligence at a fraction of the cost. In fact, 4.1 Mini often beats the older large GPT-4o on benchmarks despite being smaller and cheaper ￼. Latency is nearly half of GPT-4.1 and cost is ~83% lower ￼. This model is an excellent default choice for many applications, giving strong performance for a fifth of the price of 4.1 ￼ ￼. Price: $0.40 per 1M input tokens, $1.60 per 1M output tokens ￼.
	•	GPT-4.1 Nano – a smaller, speed-optimized model. It’s the fastest and cheapest in the 4.1 line, ideal for simple tasks, classification, or high-volume requests where cost and speed trump absolute quality ￼ ￼. It still has the huge 1M token context. While not as generally clever as the larger models, it outperforms even GPT-4o Mini on some evals despite its size ￼. Price: $0.10 per 1M input tokens, $0.40 per 1M output tokens ￼. This extremely low pricing makes GPT-4.1 Nano the best model for speed and cost-effectiveness when our task is simple enough to not need the big guns ￼ ￼.
Legacy note: GPT-4.1 models effectively replaced the earlier GPT-4.5 Preview (which was an interim model) and even outperform GPT-4o in most areas ￼ ￼. OpenAI announced the retirement of GPT-4.5 in mid-2025 after 4.1’s launch ￼. So we will prefer GPT-4.1/4.1 Mini instead of any GPT-4.5 or original GPT-4 models. GPT-4.1 also has a more recent knowledge cutoff (June 2024) than GPT-4 or 4o did ￼.
	•	GPT-4o Series (GPT-4o and GPT-4o Mini) – Multimodal Omni Models with Tool Use. GPT-4o (released late 2024) was the first OpenAI model to natively handle text, image, audio, and video inputs and generate text, image, or audio outputs from one neural network ￼. It was known as an “omni” model because of this all-in-one capability. GPT-4o is also the model that introduced built-in tool usage (as part of a limited Assistants API) – essentially the precursor to what the Responses API now generalizes ￼. In the context of the Responses API, GPT-4o and its mini version can use the built-in tools like web search or file search natively ￼ ￼. In fact, at launch of Responses API, web search was available only with GPT-4o/4o-mini models ￼ (later models like GPT-4.1 also support it). GPT-4o’s key features:
	•	Multimodal Mastery: It can hear and speak. GPT-4o uniquely supports audio input and output on the API ￼ ￼. This means it can transcribe audio to text, or even generate spoken audio as a response (text-to-speech) – capabilities not present in GPT-4.1 or GPT-5. If our project requires processing audio or generating voice responses, GPT-4o is the go-to model. (GPT-4.1 can handle images and possibly video in context, but not output audio; GPT-5 accepts audio input indirectly via conversion but does not output audio.) GPT-4o’s context window is 128k tokens ￼, smaller than GPT-4.1’s but still very large.
	•	Tool Use: GPT-4o was built with the idea of agentic behavior. It can decide to use tools like search or code execution as part of forming an answer. Under the new Responses API, GPT-4o fully supports tools in the request (web_search, file_search, etc.) ￼. GPT-4o-Mini similarly supports these tools. This makes them effective for tasks where the model might need to fetch recent info or perform calculations.
	•	Performance: GPT-4o’s text performance was comparable to GPT-4 (the original) but it has since been outclassed by GPT-4.1 in most pure text benchmarks ￼ ￼. GPT-4.1 Mini even matched or exceeded GPT-4o in intelligence while being cheaper ￼. Thus, for pure text/chat tasks we usually prefer GPT-4.1 or GPT-5. However, GPT-4o remains important for multimodal or voice-specific applications because it “breaks the mold” of text-only models ￼ ￼.
	•	Pricing: At launch, GPT-4o was about 50% cheaper than GPT-4 Turbo (and faster) for text, making it attractive for many applications ￼. Its current pricing is around $2.50 per 1M input tokens and $10 per 1M output tokens for text, with higher rates for audio tokens (processing audio is more expensive: roughly $40/M for input audio and $80/M for output audio) ￼. GPT-4o Mini is a smaller variant that was introduced mid-2024, offering lower latency and cost (we don’t have the exact current rates in this doc, but it’s significantly cheaper than full 4o). Since GPT-4.1’s release, OpenAI considers GPT-4o a legacy model for most text tasks ￼, but it still uniquely handles speech.
	•	Other Models: The Responses API also provides access to specialized models:
	•	GPT-5 Codex / GPT-5 Chat Instant: OpenAI has variants of GPT-5 tuned for coding (gpt-5-codex) or ultra-fast chat (gpt-5-chat-latest). These were referenced in Azure’s model list and OpenAI’s releases ￼ ￼. For instance, GPT-5 Chat (sometimes called GPT-5 Instant) is the faster, less “thinking” model used in ChatGPT’s front-end for quick responses ￼. We will likely not use these explicitly unless a use-case warrants it, as the main GPT-5 covers coding extremely well and we have the reasoning control to simulate an “instant” mode (via minimal effort).
	•	O-Series Models (o1, o3, o4-mini): These are earlier reasoning models predating GPT-5. For example, OpenAI o3 was described as a very capable reasoning model (it was used before GPT-5 came out for advanced reasoning tasks) ￼. The O-series are basically predecessors or alternatives that put more emphasis on multi-step thought (some were available in the Assistants API beta). GPT-5 largely supersedes them in capability ￼. We won’t likely use these explicitly, but you might see references to them (like o1, o3-mini) in some API contexts ￼. They support the same Responses API structure and reasoning parameter (effort levels), but GPT-5 is expected to outperform them in most cases ￼.
	•	GPT-3.5 Turbo (Legacy): The old GPT-3.5 series (like gpt-3.5-turbo) was the staple of the Chat Completions API in 2023. By 2025, these models are considered legacy and have severe knowledge limitations (cutoff 2021) ￼. OpenAI has deprecated some GPT-3 models and signaled that GPT-3.5 will be phased out or integrated into newer offerings ￼. Notably, GPT-4.1 Nano can achieve similar or better performance than GPT-3.5 at a comparable or lower cost ￼ ￼. Therefore, we will not use GPT-3.5 in the Responses API (in fact the Responses endpoint might not even accept it as a model param in some cases). All our applications should migrate any usage of GPT-3.5 or older completions models to at least GPT-4.1 Nano or higher. This ensures updated knowledge and far better reliability, with only slightly higher cost which is offset by caching (discussed next).

Pricing Considerations: All the above usage is billed per token as noted. The Responses API also introduces a beneficial token caching mechanism: if you send identical inputs repeatedly, OpenAI provides a 90% discount on “cached” input tokens ￼ ￼. In practice, the API uses a prompt_cache_key or internal hashing to detect if a prompt (or sub-prompt) has been seen recently, and if so, your input token cost is only 10% of normal for that part. This is reflected in the pricing breakdown as a “Cached input” rate (e.g. GPT-5 input $1.25/M, cached input $0.125/M) ￼ ￼. Our projects can leverage this by reusing prompts or specifying the prompt_cache_key for repeat queries to drastically cut costs on common instructions or backgrounds. Additionally, OpenAI offers a Batch API that can reduce costs by 50% for bulk jobs ￼, and priority tiers for throughput ￼, though those are outside the core scope of the Responses API itself.

One more note on tool usage costs: When the model uses a built-in tool (like web search), the tool’s operations (e.g. search queries) are also billed. The OpenAI pricing page lists these under “standard rates” – for example, the web search calls might be billed per query or the tokens processed from search results. In the March 2025 announcement, OpenAI clarified that tools are not charged separately beyond these token costs ￼. Essentially, if the model uses a tool and that yields text (like a web page summary), those results are fed back into the model and count as input tokens to the model’s next step. So you may see additional token usage when tools are invoked. There is no flat surcharge for enabling tools, though; you only pay for the extra tokens (and possibly API calls for external services if applicable). We can also limit how many tool calls a model can make via a parameter (see below) if we’re concerned about runaway costs or loops.

How to Use the Responses API (Query Syntax and Parameters)

Using the Responses API is straightforward once you understand the JSON structure. We send a POST request to the /v1/responses endpoint with our request payload, and the API returns a response object containing the model’s answer and any actions it took. Here we break down the key fields and how to migrate from the old Chat Completions format:

Basic Request Structure:

POST https://api.openai.com/v1/responses
{
  "model": "<model-id>",
  "input": ... ,
  "instructions": ... ,
  "tools": ... ,
  "temperature": ... ,
  "top_p": ... ,
  ... other parameters ...
}

	•	model (string, required): The ID of the model to use ￼. This should be one of the models available for Responses (see list above). For example: "gpt-5", "gpt-4.1-mini", "gpt-4o", etc. Using latest models is encouraged. Note: The Chat Completions API used model names like "gpt-3.5-turbo" or "gpt-4". In Responses API, those older ones may not all be valid; you should use the new model IDs (and likely upgrade to the newer generations). If you attempt to use a non-supported model ID, the API will return an error. Always double-check the model string (e.g., GPT-4.1 might be exactly "gpt-4.1" in the API).
	•	input (required): The content of the prompt or conversation. This field is very flexible:
	•	It can be a string containing a user’s question or prompt (for simple single-turn calls) ￼ ￼.
	•	It can also be an array of items for more complex prompts. Each item in the array can be an object representing a message or input data. For example:
	•	A text message object: {"role": "user", "content": "Hello, how are you?"}.
	•	An image object: {"role": "user", "content": [{"type": "input_image", "image_url": "<URL>"}]} – this allows attaching an image alongside a user prompt ￼ ￼.
	•	A system or developer message: e.g. {"role": "system", "content": "You are a helpful assistant."} or {"role": "developer", "content": "Always respond in JSON format."}.
	•	Essentially, the array can include multiple role-based messages just like the Chat Completions messages list, as well as non-text inputs. If you include a role "assistant" in the input array, that is taken as a prior assistant message (e.g., if you want to provide the model with its own last answer as context for the next question). However, typically to continue a conversation you’d use previous_response_id rather than manually repeating the assistant’s content.
If you only need to provide one user prompt and no additional context, you can pass input as a plain string – the API will treat it as a single user message ￼ ￼. This is a nice shortcut. For more control, pass an array of message objects (similar to the old messages array but with expanded roles).
	•	instructions (string, optional): This field lets you supply a single system-level instruction without having to wrap it in the input array ￼. It is effectively inserted as a system message at the beginning of context. For instance, you might set "instructions": "You are an expert travel guide." to prime the assistant’s behavior. If you use instructions and also have a system message in the input list, be aware the two might conflict – generally you should choose one method. instructions is mostly a convenience for one-shot system prompts. (In code, you wouldn’t combine instructions with an input array that already contains a system role; use one or the other.)
	•	tools (array, optional): This is where you specify which (if any) tools or functions the model is allowed to use ￼ ￼. If omitted or an empty list, the model cannot call any tools and will only produce a direct answer (just like classic behavior). If you want the model to be able to, say, do a web search, you must include the corresponding tool descriptor in this array. Each tool is an object; built-in tools typically are identified by a "type". Examples:
	•	To enable web search: "tools": [ { "type": "web_search_preview", "search_context_size": "medium", "user_location": {...} } ]. The type is web_search_preview (the current tool name as of 2025) ￼. You can also provide optional parameters: search_context_size can suggest how much of the context window to use for search results (low/medium/high) ￼, and user_location can give an approximate location to localize search results (with fields like city, country code, etc.) ￼ ￼. If no location is given, the search may assume a default or global context.
	•	To allow file search: e.g. { "type": "file_search_preview" } (you might include specifics like which files or what query, but generally just enabling it is enough – the model will then use action: "search_files" internally if needed).
	•	To allow the computer/code tool: For example, OpenAI had a {"type": "computer_use_preview"} which corresponds to allowing the model to execute code (what was known as Code Interpreter).
	•	For custom functions: In the new API design, custom developer-provided functions are also configured via tools. The exact format is a bit more involved (you’d provide the function name, parameters schema, etc., similar to how you did with functions in Chat Completions, but packaged under the tools list). For instance, the tool object might be { "type": "function", "name": "calculate_sum", "parameters": { ...schema... } }. When this is provided, the model can respond with a tool call like <function calculate_sum args> and your code will receive that in the output to handle. GPT-5 even allows a simpler “custom tool with plaintext” mode, but the details are beyond this summary ￼. The key point: to migrate your Chat Completions function-calling code, you will use the tools array in Responses API to register those functions (rather than a separate functions field). The model’s function call will appear as a tool usage event in the output.
Important: Not all models support all tools. For example, as of 2025, web search and file search tools are supported by GPT-4.1, GPT-4o (and 4o-mini), and of course GPT-5 ￼. Some smaller or older models may ignore tools or not be allowed to use them. Always check model capabilities. GPT-5 and GPT-4.1 should cover most tools. (Azure notes indicate web search wasn’t initially in their Responses preview, but on OpenAI it is supported with those models.) If a tool requires a specific model (like the computer use tool requires a special underlying model), ensure you deploy the correct model. Azure documentation mentions a computer-use-preview model powering that tool ￼, but on OpenAI’s side, enabling the tool likely prompts the system to use the correct backend automatically.
	•	tool_choice (optional, string or object): This parameter can influence how the model chooses tools. By default it’s "auto" meaning the model decides on its own when to use which tool ￼. There are advanced settings where you can restrict tool selection or force certain calls, but generally we leave this auto. You might set it to a specific tool name to force use of only that tool, or provide some criteria. We typically won’t use this unless debugging tool usage behavior.
	•	max_tool_calls (integer, optional): This lets you cap the total number of tool invocations the model can make within a single response cycle ￼. For example, if you set "max_tool_calls": 2, the model could at most call two tools (like do two web searches or one search + one function call) before it must produce a final answer. This is a safety to avoid infinite loops or excessive API calls. By default, it’s not set (or null), meaning no specific limit beyond model’s own judgment. We might set this if we notice the model tends to over-use tools or if we have cost concerns.
	•	parallel_tool_calls (boolean, optional): If true, the model is allowed to execute multiple tool calls in parallel (if it supports it) ￼ ￼. Some advanced models like GPT-5 can issue parallel calls (for instance, searching multiple queries at once, or calling different tools concurrently) ￼. By default this is false (tools used sequentially). Enabling parallel calls could speed up responses that require multiple lookups. We will likely keep this off unless we have a use-case where parallelism helps, because it can complicate the output structure (you’d get parallel events). It’s good to know the option exists though.
	•	temperature (number, optional): The randomness or creativity setting for the model’s output, in the range 0 to 2 ￼. This works just like in the older APIs: a low temperature (e.g. 0 or 0.2) makes outputs more deterministic and focused (good for factual or coding tasks), while a higher temperature (e.g. 1.0 or above) yields more randomness and diverse phrasing (useful for creative tasks). Default is often 1.0 if not specified. Note that for GPT-5 models, OpenAI has adjusted how randomness works – in fact, in some SDK versions, the temperature parameter might be ignored or fixed for GPT-5. There were indications that GPT-5 might not support temperature in the same way ￼. The reasoning is that GPT-5’s behavior is largely guided by the reasoning.effort and it might have an adaptive strategy. However, official docs still list temperature for Responses API generally. So, we include it, but keep in mind if you see no effect with GPT-5, that could be intentional (some updates removed temperature for GPT-5 to simplify usage, setting it effectively to 1). For other models, it works as usual.
	•	top_p (number, optional): The nucleus sampling parameter, between 0 and 1, as an alternative or complement to temperature ￼. This controls diversity by selecting from the top probability mass. For example, top_p=0.1 means “consider only the top 10% probable tokens”. We typically leave this at the default 1.0 (which means no nucleus cutoff) and primarily use temperature for randomness control. But you can adjust it to limit the model’s scope of randomness. Only set this OR temperature in most cases – if both are set, they both apply (which can overly constrain output if set low).
	•	top_logprobs (integer, optional): If you want to see the model’s top token probabilities at each generation step, you can set this to an integer N (up to 20) ￼. The model will then include the top N tokens and their probabilities for each position in the output (in the output data under logprobs). This is useful for debugging or analyzing uncertainty. It’s rarely needed in production and adds overhead, so we usually leave it at 0 or null. But it’s there.
	•	max_output_tokens (integer, optional): This sets an upper bound on how many tokens the model can generate in its visible output (plus reasoning tokens) ￼. Essentially this replaces the old max_tokens parameter. For example, if you want at most ~200 tokens in the answer, set "max_output_tokens": 200. The model will stop once it produces that many tokens (or earlier if it finishes). If not set, the model can use up to its limit (which might be thousands, or near the context window size minus input length). Keep in mind: this limit includes any “reasoning” tokens the model uses internally for reasoning models ￼. So if you set a very tight limit with GPT-5, it might cut off the answer because some tokens were consumed in hidden reasoning. It’s often better to leave this fairly high to let the model complete, unless you specifically want a brief answer.
	•	reasoning (object, optional): This field is specifically for configuring reasoning-mode models (GPT-5 and the older O-series) ￼. It allows us to control the model’s approach to reasoning. The reasoning object has at least one important sub-field:
	•	reasoning.effort: can be "minimal", "low", "medium", or "high" ￼ ￼. This setting guides how extensively the model thinks before answering. - High: the model will spend more steps “deliberating,” leading to potentially more thorough and accurate answers for complex tasks, but also slower responses and more token usage.
	•	Medium: a balanced default (similar to how older models worked; GPT-4o and others basically had medium as their fixed style).
	•	Low: the model does some reasoning but tries not to overdo it – faster than medium, but might miss some depth.
	•	Minimal: a special mode introduced with GPT-5 where the model uses very few reasoning tokens, essentially giving almost an “instant” answer ￼ ￼. This is the fastest but potentially least reflective mode. Interestingly, minimal effort often works very well for straightforward tasks or when you want the model to just comply with instructions without overthinking ￼ ￼. By default, GPT-5 uses medium effort if not specified ￼. We should choose the effort level depending on the scenario (e.g., for coding with GPT-5, medium or high effort can catch more errors and explain more, whereas for a quick question-answer or simple task, minimal saves time and cost).
The reasoning object might also have other fields; one noted is summary (often null) which could eventually hold a brief summary of the reasoning or an encryption of it for passing to next turn ￼ ￼. As of now, we mainly use effort. If not using a reasoning-type model (like if using GPT-4.1), this parameter is ignored.
	•	text (object, optional): This configures the format of the model’s final answer (and related settings). Inside this, one key field is text.format.type, which can be "text" or "structured" ￼. By default it’s "text", meaning the model’s answer will be normal conversational text. If you want the model to output JSON or some structured format directly (without using a function call), you could set format to structured and provide a schema or instructions accordingly. Another sub-field is text.verbosity:
	•	text.verbosity: can be "low", "medium", or "high" ￼ ￼. This corresponds to how detailed and lengthy the assistant’s answer should be. High verbosity means the model will be more expansive, give thorough explanations or longer code, etc. Low verbosity makes it concise – short answers, minimal commentary ￼ ￼. Prior to GPT-5, you couldn’t directly tweak this (models had an inherent verbosity; e.g. GPT-4 tended to be wordy). GPT-5 allowed exposing this knob. If not set, it defaults to medium (the usual balance). We can use this to ensure responses meet desired length: for example, in summarization, low verbosity for a brief summary, or in analysis, high verbosity to get detailed reasoning. This is easier than trying to prompt engineer “please be brief” or “give more detail,” though you can still do both for reinforcement.
There may be additional fields under text in the future (like controlling Markdown vs plain text, etc.). Currently, verbosity is the main one. For output format, if we needed structured JSON directly, another approach is to instruct the model via system message to output JSON – but the Responses API’s structure could allow it to return a JSON object as part of output items rather than raw text. For now, we typically use normal text outputs (with the model using function calls if structured data retrieval is needed).
	•	previous_response_id (string, optional): As mentioned, this tells the API to continue the conversation from a previous stored response ￼. If you made a call with store: true (default) and got back a response.id, you can use that ID here to have all the context from that response (including all its input messages and output) be included for the model this time. Essentially this is how you have the model remember past conversation without resending it. This is analogous to using a conversation ID or thread in other systems. Use this when doing multi-turn dialogues in separate API calls. If you include both previous_response_id and also provide overlapping history in the input, the model might see duplicate information, so typically you do one or the other. If your organization has disabled data storage (or you set store: false), then you cannot use this and must send history manually.
	•	store (boolean, optional): Defaults to true. If set to false, the API will not store the response data on OpenAI’s servers beyond processing, meaning you cannot retrieve it later and previous_response_id won’t work (or at least, it wouldn’t find anything) ￼ ￼. You might turn this off for privacy (though OpenAI assures that even stored data is not used to train models by default ￼) or if you want to fully manage conversation state yourself. In our projects we usually keep store=true (so that we can debug or retrieve logs if needed through the dashboard). Data is typically retained 30 days by OpenAI for support purposes ￼.
	•	include (array, optional): This field allows requesting additional metadata in the response that normally isn’t returned ￼ ￼. Each element in this array is a flag for including something. Examples:
	•	"message.output_text.logprobs" – would include token logprob info with the assistant’s message ￼.
	•	"web_search_call.action.sources" – to include the actual web sources and snippets retrieved during a web_search call ￼.
	•	"file_search_call.results" – include the list of files or content snippets found by a file search tool ￼.
	•	"code_interpreter_call.outputs" – include outputs from code execution if using the code interpreter tool ￼.
	•	"reasoning.encrypted_content" – includes an encrypted blob of the model’s reasoning tokens ￼, which can be decrypted by OpenAI in a future request to maintain continuity without revealing the reasoning content (used for zero-data-retention flows).
We usually don’t need to use include unless we have a specific debugging or logging need. It’s there if we want deeper insight.
	•	metadata (map, optional): You can attach up to 16 key-value pairs of your own metadata to the request ￼. This will be stored and can show up in logs, but doesn’t affect the model’s behavior. It’s purely for your tracking (e.g., you could tag a response with {"customer_id": "12345", "experiment_group": "A"} to identify it later in logs). Not necessary unless we have an app use for it.
	•	safety_identifier (string, optional): A tag to help OpenAI attribute any safety violations or issues back to a stable identifier for your user or session ￼. This replaced the older user field. It can be something like a user ID but not personally identifiable information (something hashed or random) – it’s used internally for safety monitoring and policy enforcement. It’s recommended to set if you serve multiple end-users through the API, so that OpenAI can see if one user is triggering a lot of flagged content and take action accordingly ￼. In our internal projects, we might not use it if there’s just one system user, but for multi-user apps we should.
	•	prompt_cache_key (string, optional): Allows explicit control of caching. If you set this to a consistent key for identical prompts, the API will treat those requests as cache-equivalent ￼. By default, OpenAI does this automatically by hashing the prompt content, but a custom key can be useful if your prompt contains some variable info that doesn’t actually change the result (so the hash would differ, but you know it can be reused). Using this wisely can improve cache hits and reduce cost. This is an advanced optimization; otherwise, leaving it null and letting the default caching work is fine.
	•	stream (boolean, optional): Set to true to stream the response as events via Server-Sent Events (SSE) ￼. This works similarly to setting stream=True in ChatCompletion calls. Your HTTP library or the OpenAI SDK will then yield events incrementally rather than waiting for the full response. Use this for real-time UI updates or when generating long answers to show partial progress. When streaming, the response JSON structure is sent in pieces (with event: ... lines). We handle it by iterating over events. The final event is typically [DONE] or the stream ends when complete. Remember, when streaming, your code needs to assemble the final answer from the text.delta events (which contain chunks of text) ￼ ￼. Also, tool usage or function call events may come through as well in the stream (e.g., an event might indicate a web_search_call was made, possibly with partial results).
	•	stream_options (object, optional): If streaming, you can specify some options. One known option is include_obfuscation (boolean) which by default is true ￼. This relates to OpenAI’s approach to mitigate side-channel timing attacks by adding random padding to events. With it true, some events might include an obfuscation field with random characters to mask the exact length of real content chunks ￼. This has a tiny bandwidth overhead. If you trust your network and want to save bandwidth, you can set include_obfuscation: false to skip those random pads ￼. This is low-level and usually not something to worry about unless streaming performance is critical.

To illustrate, here’s a simple example of making a Responses API call in Python, compared to Chat Completions:

import openai

openai.api_key = "sk-..."  # ensure your API key is set

# Old Chat Completions style (for comparison; not to be used now):
chat_response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Write a one-sentence bedtime story about a unicorn."}]
)
print(chat_response["choices"][0]["message"]["content"])

# New Responses API style:
response = openai.Response.create(
    model="gpt-4.1",
    input="Write a one-sentence bedtime story about a unicorn."
)
print(response.output_text)

In the above, the ChatCompletion required wrapping the prompt in a messages list with a role. The Responses API call takes the raw prompt as input directly ￼ ￼. Both will yield a single-sentence story from the model, but the latter is more concise to call. Notice also we switched to model="gpt-4.1" – assuming GPT-4.1 is available and is an improvement over the older GPT-4. The structure of the Python SDK may differ slightly (some SDK versions allow openai.Response.create directly, others might need client = openai.OpenAI(); client.responses.create(...) as in some examples ￼ ￼). In any case, the parameters discussed above apply.

Handling the Response: The output from the Responses API will be a JSON with an id, object: "response", created_at timestamp, the model used (including version info), and an output list that contains the actual content. For simple cases with no tools, output will contain one item: the assistant’s message. For example:

{
  "id": "resp_67cb32...a85",
  "object": "response",
  "created_at": 1741369938.0,
  "model": "gpt-4.1-2025-04-14",
  "output": [
    {
      "id": "msg_67cb32...a798",
      "role": "assistant",
      "type": "message",
      "content": [
        { "type": "output_text", "text": "Once upon a time, a unicorn drifted off to sleep under a candy-colored sky." }
      ]
    }
  ],
  "usage": {
    "input_tokens": 10,
    "output_tokens": 22,
    "total_tokens": 32,
    "output_tokens_details": { "reasoning_tokens": 0 }
  }
}

In the Python SDK, you can typically get the final text via response.output_text (which likely concatenates all output_text fragments in the assistant message content) ￼. If a tool was used, the output list will contain multiple items. For example, if the model did a web search, you might see an item with "type": "web_search_call" (and details of the query) followed by another item which is the assistant’s message with the answer that includes information from the web ￼ ￼. Each tool call item will have an action and possibly a result. The assistant’s final answer is usually the last item (role “assistant”, type “message”). If you requested streaming, you would have gotten these items incrementally as events.

Error handling: The Responses API will return an "error" field if something went wrong (just like other OpenAI endpoints). Also note, if you set parameters in an unsupported way (e.g. a model doesn’t support a given tool or if you exceed context length), you’ll get a 400 error. Using truncation: "auto" can prevent some context length errors by instructing the API to drop oldest messages if needed to fit the window ￼ ￼. By default, truncation is "disabled" which means it will error rather than truncate context ￼. We might set "truncation": "auto" for long conversations to avoid manual handling of overflow. This will remove some middle parts of conversation if it doesn’t fit (keeping the beginning and end by design).

That covers the major aspects of how to call the Responses API. Next, we’ll specifically address migrating code from the Chat Completions format to this new format, to ensure nothing is missed.

Migrating from Chat Completions to Responses API

If you have existing code or prompts built around the Chat Completions (or even older Completions) endpoint, here is how to transition them to use the Responses API. We do not use the ChatGPT/Chat Completions endpoint in our projects anymore, so all such code must be updated to Responses.

1. Endpoint and Client Changes:
	•	Endpoint URL: Instead of hitting /v1/chat/completions, you will send requests to /v1/responses ￼. With the current Python SDK that means instantiating `client = OpenAI()` and calling `client.responses.create(...)` rather than `client.chat.completions.create(...)`. In Node, reach for `await openai.responses.create({...})` instead of the chat completions helper. Make sure your OpenAI SDK is recent enough to expose the Responses API (Python ≥0.28, Node ≥4.0 at the time of writing) ￼.
	•	Naming: Note the object is often plural “responses” in code (to denote the collection). For instance, some SDKs have you do client = OpenAI(); client.responses.create(...) as shown in Azure docs ￼. Check the documentation for your library – but usually, looking for a class or method containing “response” is the way. The older openai.Completion and openai.ChatCompletion classes are superseded by this.

2. Request Body Conversion:
	•	Messages -> Input: In Chat Completions, you passed a list of messages, e.g.:

{
  "model": "gpt-4",
  "messages": [
     {"role": "system", "content": "..."},
     {"role": "user", "content": "Hello!"}
  ]
}

In Responses API, there is no “messages” field. Instead, you do either:
	•	Put those message objects in the "input" array:

{
  "model": "gpt-4.1",
  "input": [
     {"role": "system", "content": "..."},
     {"role": "user", "content": "Hello!"}
  ]
}

This achieves the same result ￼ ￼.

	•	Or, you can take the system message and put it in instructions, and the last user message as a simple string input:

{
  "model": "gpt-4.1",
  "instructions": "...",
  "input": "Hello!"
}

Either approach works. If you have multiple prior turns or multiple messages to include (e.g., in the middle of a convo), use the array form.

	•	Function Calling -> Tools: If your Chat Completions request used the functions parameter to define functions and maybe function_call to force a call, you will translate that into the tools parameter in Responses API. OpenAI hasn’t published a full guide on this yet as of writing, but conceptually:
	•	Each function definition becomes a tool entry. For example, if you had a function {"name": "getWeather", "parameters": {...}}, you would include a tool like {"type": "function", "name": "getWeather", "parameters": {...}} in the tools list. The model’s decision to call it will appear as a tool call item in output, with type": "function_call" or similar, and you’ll handle it similarly to before (looking at response.output events).
	•	If you previously relied on function_call: "auto" or "none" or specific function name to force call, you might need to adjust with tool_choice or by instructing the model via developer message to use or not use certain tools. For instance, to force it not to call a function, you simply wouldn’t include that function in tools (so it has no choice).
	•	Stream: Chat Completions had stream=True – same in Responses. The handling is slightly different since you get events. But from a high-level, you can mostly swap out the call and keep reading events. Just check the event format (in Chat Completions, you got objects with .choices[0].delta; in Responses, you get events which might have a field event['delta'] or event.delta in SDK).
	•	Other fields: Some parameters in Chat Completions have direct analogs:
	•	max_tokens (chat) -> max_output_tokens (responses) ￼.
	•	temperature, top_p, stop – Stop sequences: Notably, the stop parameter (list of stop strings) seems to be absent in the Responses API documentation. If you need the model to stop at certain tokens, you may have to enforce that in post-processing or by prompt design, since stop is not exposed (it might be intentionally omitted because the new models and tools complicate it). So if you had used stop, remove it and consider including the stop pattern in your prompt (e.g., “End answer with [END]” and then split).
	•	presence_penalty and frequency_penalty: These do not appear in the Responses API reference ￼. It seems OpenAI has removed or hidden these parameters for the new models, likely because their effects can be unpredictable with the new reasoning paradigm. The newer models handle repetition and token selection differently, and we haven’t needed to use these penalties as much. So if your old request had them, drop them. If repetition becomes an issue, consider adjusting temperature or instructing the model. (For fine-grained control, the model’s improved anyway – e.g., GPT-4.1 and GPT-5 naturally avoid repetition more than GPT-3.5 did.)
	•	user (id string for end-user) -> replaced by safety_identifier and/or prompt_cache_key as described ￼. Usually you can drop user and if needed use safety_identifier.

3. Adapting to Output Differences:
	•	In Chat Completions, you got a response like response['choices'][0]['message']['content'] for the assistant’s reply. In Responses API, you will get response['output'] which is a list of items. The text is nested inside the assistant message item. The OpenAI Python client helps by providing response.output_text for convenience ￼. If using raw HTTP, you’d extract response['output'][-1]['content'] and join the text segments. We should verify our code to assemble the final answer correctly.
	•	If your old code assumed a single answer, that remains true in most cases (the model will return one final assistant message by default). However, note that n (for multiple outputs) isn’t explicitly documented in Responses API – it might not support returning multiple answer choices in one call. Typically, if we wanted multiple independent outputs we’d call multiple times or use the Batch API. So we won’t use n as we might have in Completions.
	•	Tool usage: In Chat Completions with function calling, the flow was: model returns a message of role "function" with arguments, you execute it, then call the API again with function result. In Responses API, the single call handles this loop internally if using built-in tools. For custom functions, the pattern might still involve returning a tool result item and requiring our code to call openai.responses.create again with that result (unless using the Agents SDK to manage it automatically). If we stick to built-in tools and pure responses, our calls will typically just get the final answer and maybe intermediate steps which we can log. For custom tools, be prepared to possibly handle function output similarly to before but via the new format. This is an advanced case; initially we might avoid complex custom functions and rely on built-ins or simpler flows.

4. Testing and Verification:
After converting a call to Responses API, test it with known inputs to ensure the behavior matches expectations:
	•	Check that system instructions are applied (the model’s style or persona should reflect any instructions or system message you provided).
	•	If you had deterministic outputs with temperature 0 before, ensure you still set temperature: 0 for that call.
	•	If a function should be called (say you ask a question that should trigger your tool), verify that the model indeed uses the tool. In the output, you should see a tool call item. If it doesn’t, you might need to nudge it via the prompt (the model is generally quite capable of deciding, but sometimes a system/dev message like “You have access to X tool for Y” can help).
	•	Performance: The Responses API call might be slightly slower if it’s doing more work (e.g., using tools internally). However, because it’s one round-trip instead of multiple, it often ends up faster overall for tasks that previously required multiple calls. For a straight Q&A with no tools, speed should be similar to Chat Completions for the same model.

5. Project Configuration:
Ensure any code that might accidentally use the old endpoints (for example, some libraries have ChatGPT-specific helpers) is updated to use Responses. If using frameworks or plugins, look for ones updated to Responses API. For instance, if we use LangChain or another orchestration library, use their integration for Responses if available, or configure it manually (some may still default to Chat Completions).

6. Deprecation of Chat Completions:
While Chat Completions will remain supported for some time (OpenAI has committed to continuing support and new model releases on it when tool use isn’t needed ￼), our internal policy is to always use Responses. That means even for simple tasks that theoretically don’t need tools or advanced features, we’ll still use the Responses endpoint (with no tools enabled) to keep things consistent. This also future-proofs our projects: if later we decide a tool is needed, we can just add it to the request without switching endpoints. In effect, consider the Responses API as “Chat Completions 2.0”. It has the same capability plus headroom for growth. There is no downside in using it even for basic prompts – performance and pricing are identical when using the same model ￼.

We should explicitly avoid any code path that calls ChatCompletion.create or OpenAI’s old Completion.create. The latter (completions for text-Davinci, etc.) was actually scheduled for shutdown (older models were retired Jan 4, 2024) ￼. ChatCompletion remains, but again, using it might lock us out of the newest models like GPT-4.1 or GPT-5, which may only be available via Responses or have better functionality there. OpenAI noted that GPT-4.1 was only in the API (not in ChatGPT UI, but it was likely accessible in ChatCompletion API too) – however, GPT-5’s features like verbosity control are definitely only in the Responses API. So to leverage those, Responses is the way.

7. Edge Cases:
	•	Streaming differences: If migrating an application that streamed results to a UI, adjust the event parsing. In ChatCompletion streaming, one would concatenate delta texts until finished is true. In Responses, you will listen for events and might need to filter them. For example, you may get an event of type text.delta with some text – append that to the output buffer ￼. You might also get a tool_start or tool_end event if a tool is used. You can ignore those for just printing the final answer (the final answer text will also stream as text.delta events when it’s being generated).
	•	Function outputs: In Chat Completions, after a function call, you provided the function’s result as an assistant message with role “function”. In Responses API, if you have custom functions, after your code executes the function, you might need to call responses.create again with the function output included as a special input item (role: “user” or “function” content: result). The architecture for custom functions in Responses isn’t documented here, but be aware it might not all be magically one-call unless using the Agents SDK. For built-in tools (web search, etc.), OpenAI handles it within one call – that’s the big improvement. For our internal functions, we might still have to handle it similarly to before, or use the new “custom tool with plaintext” approach in GPT-5 which could allow the model to incorporate the result without another round trip ￼ ￼.
	•	Testing tool permission: When a model has tools enabled, occasionally it might choose not to use them even if it could. Or vice versa, if not enabled, it won’t attempt. If we find the model referencing a tool name in its answer when the tool wasn’t enabled, it could be an hallucination – to fix that, ensure the system/developer instructions clarify what tools are available or not. OpenAI likely conditions models to know which tools are present based on the tools field, but a well-crafted prompt can further reduce confusion.

By following the above steps, any functionality we had with Chat Completions should work under Responses API, usually with less complexity and more power available if needed.

To reiterate: Do not use `openai.ChatCompletion` or `openai.Completion` in any code. Replace those with `client.responses.create` (or the equivalent helper in your language SDK). All new features like GPT-5 reasoning controls require the Responses endpoint – for example, adjusting verbosity or reasoning effort will not work through ChatCompletion calls ￼. We want to consistently use the approach that OpenAI calls “the future direction for building agents” ￼, which is the Responses API.

Conclusion

The OpenAI Responses API is a comprehensive upgrade that merges chat capabilities with tool use and multimodal processing in a single interface. In our projects, we will always use the Responses API endpoint to harness these benefits. This ensures access to the latest models (like GPT-4.1 and GPT-5) and features, and aligns with OpenAI’s recommended best practices ￼. By migrating fully from the old Completions/Chat endpoints to Responses, we gain:
	•	Unified development pattern – one API to handle conversations, function calls, searches, etc., simplifying our code and maintenance.
	•	Better performance options – use large context windows up to 1M tokens, adjust reasoning depth and answer verbosity, and leverage faster mini/nano models as needed to optimize cost and latency.
	•	Future-proofing – as OpenAI rolls out new tools or model improvements, they will appear in Responses API first (the Assistants API is being deprecated in favor of this by 2026 ￼, and even Chat Completions will get only a subset of new models) ￼. We’re already seeing that with GPT-5 features.
	•	Consistency across features – no more juggling different endpoints for chat vs vision vs function calling. Responses API handles them all, so we can build richer AI solutions with less complexity.

When instructing Large Language Models (like Codex or Claude) that will interact with our system or write code for it, we include this documentation to ensure they understand: the Responses API is the one to use. They should call the appropriate endpoint, use the correct parameters as detailed above, and avoid any legacy methods. This way, any AI agent or coding assistant working on our codebase will follow the same standards.

By thoroughly covering the what, why, and how of the Responses API – from explaining its purpose to listing models and pricing to detailing request syntax and migration steps – this document should serve as a complete guide. It provides everything needed to work with the Responses API effectively in our projects and to transition away from older endpoints completely.



Using GPT-5
===========

Learn best practices, features, and migration guidance for GPT-5.

GPT-5 is our most intelligent model yet, trained to be especially proficient in:

*   Code generation, bug fixing, and refactoring
*   Instruction following
*   Long context and tool calling

This guide covers key features of the GPT-5 model family and how to get the most out of GPT-5.

### Explore coding examples

Click through a few demo applications generated entirely with a single GPT-5 prompt, without writing any code by hand.

Quickstart
----------

Faster responses

By default, GPT-5 produces a medium length chain of thought before responding to a prompt. For faster, lower-latency responses, use low reasoning effort and low text verbosity.

This behavior will more closely (but not exactly!) match non-reasoning models like [GPT-4.1](/docs/models/gpt-4.1). We expect GPT-5 to produce more intelligent responses than GPT-4.1, but when speed and maximum context length are paramount, you might consider using GPT-4.1 instead.

Fast, low latency response options

```javascript
import OpenAI from "openai";
const openai = new OpenAI();

const result = await openai.responses.create({
  model: "gpt-5",
  input: "Write a haiku about code.",
  reasoning: { effort: "low" },
  text: { verbosity: "low" },
});

console.log(result.output_text);
```

```python
from openai import OpenAI
client = OpenAI()

result = client.responses.create(
    model="gpt-5",
    input="Write a haiku about code.",
    reasoning={ "effort": "low" },
    text={ "verbosity": "low" },
)

print(result.output_text)
```

```bash
curl https://api.openai.com/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-5",
    "input": "Write a haiku about code.",
    "reasoning": { "effort": "low" }
  }'
```

Coding and agentic tasks

GPT-5 is great at reasoning through complex tasks. **For complex tasks like coding and multi-step planning, use high reasoning effort.**

Use these configurations when replacing tasks you might have used o3 to tackle. We expect GPT-5 to produce better results than o3 and o4-mini under most circumstances.

Slower, high reasoning tasks

```javascript
import OpenAI from "openai";
const openai = new OpenAI();

const result = await openai.responses.create({
  model: "gpt-5",
  input: "Find the null pointer exception: ...your code here...",
  reasoning: { effort: "high" },
});

console.log(result.output_text);
```

```python
from openai import OpenAI
client = OpenAI()

result = client.responses.create(
    model="gpt-5",
    input="Find the null pointer exception: ...your code here...",
    reasoning={ "effort": "high" },
)

print(result.output_text)
```

```bash
curl https://api.openai.com/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-5",
    "input": "Find the null pointer exception: ...your code here...",
    "reasoning": { "effort": "high" }
  }'
```

Meet the models
---------------

There are three models in the GPT-5 series. In general, `gpt-5` is best for your most complex tasks that require broad world knowledge. The smaller mini and nano models trade off some general world knowledge for lower cost and lower latency. Small models will tend to perform better for more well defined tasks.

To help you pick the model that best fits your use case, consider these tradeoffs:

|Variant|Best for|
|---|---|
|gpt-5|Complex reasoning, broad world knowledge, and code-heavy or multi-step agentic tasks|
|gpt-5-mini|Cost-optimized reasoning and chat; balances speed, cost, and capability|
|gpt-5-nano|High-throughput tasks, especially simple instruction-following or classification|

### Model name reference

The GPT-5 [system card](https://openai.com/index/gpt-5-system-card/) uses different names than the API. Use this table to map between them:

|System card name|API alias|
|---|---|
|gpt-5-thinking|gpt-5|
|gpt-5-thinking-mini|gpt-5-mini|
|gpt-5-thinking-nano|gpt-5-nano|
|gpt-5-main|gpt-5-chat-latest|
|gpt-5-main-mini|[not available via API]|

### New API features in GPT-5

Alongside GPT-5, we're introducing a few new parameters and API features designed to give developers more control and flexibility: the ability to control verbosity, a minimal reasoning effort option, custom tools, and an allowed tools list.

This guide walks through some of the key features of the GPT-5 model family and how to get the most out of these models.

Minimal reasoning effort
------------------------

The `reasoning.effort` parameter controls how many reasoning tokens the model generates before producing a response. Earlier reasoning models like o3 supported only `low`, `medium`, and `high`: `low` favored speed and fewer tokens, while `high` favored more thorough reasoning.

The new `minimal` setting produces very few reasoning tokens for cases where you need the fastest possible time-to-first-token. We often see better performance when the model can produce a few tokens when needed versus none. The default is `medium`.

The `minimal` setting performs especially well in coding and instruction following scenarios, adhering closely to given directions. However, it may require prompting to act more proactively. To improve the model's reasoning quality, even at minimal effort, encourage it to “think” or outline its steps before answering.

Minimal reasoning effort

```bash
curl --request POST   --url https://api.openai.com/v1/responses   --header "Authorization: Bearer $OPENAI_API_KEY"   --header 'Content-type: application/json'   --data '{
	"model": "gpt-5",
	"input": "How much gold would it take to coat the Statue of Liberty in a 1mm layer?",
	"reasoning": {
		"effort": "minimal"
	}
}'
```

```javascript
import OpenAI from "openai";
const openai = new OpenAI();

const response = await openai.responses.create({
  model: "gpt-5",
  input: "How much gold would it take to coat the Statue of Liberty in a 1mm layer?",
  reasoning: {
    effort: "minimal"
  }
});

console.log(response);
```

```python
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-5",
    input="How much gold would it take to coat the Statue of Liberty in a 1mm layer?",
    reasoning={
        "effort": "minimal"
    }
)

print(response)
```

### Verbosity

Verbosity determines how many output tokens are generated. Lowering the number of tokens reduces overall latency. While the model's reasoning approach stays mostly the same, the model finds ways to answer more concisely—which can either improve or diminish answer quality, depending on your use case. Here are some scenarios for both ends of the verbosity spectrum:

*   **High verbosity:** Use when you need the model to provide thorough explanations of documents or perform extensive code refactoring.
*   **Low verbosity:** Best for situations where you want concise answers or simple code generation, such as SQL queries.

Models before GPT-5 have used `medium` verbosity by default. With GPT-5, we make this option configurable as one of `high`, `medium`, or `low`.

When generating code, `medium` and `high` verbosity levels yield longer, more structured code with inline explanations, while `low` verbosity produces shorter, more concise code with minimal commentary.

Control verbosity

```bash
curl --request POST   --url https://api.openai.com/v1/responses   --header "Authorization: Bearer $OPENAI_API_KEY"   --header 'Content-type: application/json'   --data '{
  "model": "gpt-5",
  "input": "What is the answer to the ultimate question of life, the universe, and everything?",
  "text": {
    "verbosity": "low"
  }
}'
```

```javascript
import OpenAI from "openai";
const openai = new OpenAI();

const response = await openai.responses.create({
  model: "gpt-5",
  input: "What is the answer to the ultimate question of life, the universe, and everything?",
  text: {
    verbosity: "low"
  }
});

console.log(response);
```

```python
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-5",
    input="What is the answer to the ultimate question of life, the universe, and everything?",
    text={
        "verbosity": "low"
    }
)

print(response)
```

You can still steer verbosity through prompting after setting it to `low` in the API. The verbosity parameter defines a general token range at the system prompt level, but the actual output is flexible to both developer and user prompts within that range.

### Custom tools

With GPT-5, we're introducing a new capability called custom tools, which lets models send any raw text as tool call input but still constrain outputs if desired.

[

Function calling guide

Learn about custom tools in the function calling guide.

](/docs/guides/function-calling)

#### Freeform inputs

Define your tool with `type: custom` to enable models to send plaintext inputs directly to your tools, rather than being limited to structured JSON. The model can send any raw text—code, SQL queries, shell commands, configuration files, or long-form prose—directly to your tool.

```bash
{
    "type": "custom",
    "name": "code_exec",
    "description": "Executes arbitrary python code",
}
```

#### Constraining outputs

GPT-5 supports context-free grammars (CFGs) for custom tools, letting you provide a Lark grammar to constrain outputs to a specific syntax or DSL. Attaching a CFG (e.g., a SQL or DSL grammar) ensures the assistant's text matches your grammar.

This enables precise, constrained tool calls or structured responses and lets you enforce strict syntactic or domain-specific formats directly in GPT-5's function calling, improving control and reliability for complex or constrained domains.

#### Best practices for custom tools

*   **Write concise, explicit tool descriptions**. The model chooses what to send based on your description; state clearly if you want it to always call the tool.
*   **Validate outputs on the server side**. Freeform strings are powerful but require safeguards against injection or unsafe commands.

### Allowed tools

The `allowed_tools` parameter under `tool_choice` lets you pass N tool definitions but restrict the model to only M (< N) of them. List your full toolkit in `tools`, and then use an `allowed_tools` block to name the subset and specify a mode—either `auto` (the model may pick any of those) or `required` (the model must invoke one).

[

Function calling guide

Learn about the allowed tools option in the function calling guide.

](/docs/guides/function-calling)

By separating all possible tools from the subset that can be used _now_, you gain greater safety, predictability, and improved prompt caching. You also avoid brittle prompt engineering, such as hard-coded call order. GPT-5 dynamically invokes or requires specific functions mid-conversation while reducing the risk of unintended tool usage over long contexts.

||Standard Tools|Allowed Tools|
|---|---|---|
|Model's universe|All tools listed under "tools": […]|Only the subset under "tools": […] in tool_choice|
|Tool invocation|Model may or may not call any tool|Model restricted to (or required to call) chosen tools|
|Purpose|Declare available capabilities|Constrain which capabilities are actually used|

```bash
"tool_choice": {
    "type": "allowed_tools",
    "mode": "auto",
    "tools": [
      { "type": "function", "name": "get_weather" },
      { "type": "function", "name": "search_docs" }
    ]
  }
}'
```

For a more detailed overview of all of these new features, see the [accompanying cookbook](https://cookbook.openai.com/examples/gpt-5/gpt-5_new_params_and_tools).

### Preambles

Preambles are brief, user-visible explanations that GPT-5 generates before invoking any tool or function, outlining its intent or plan (e.g., “why I'm calling this tool”). They appear after the chain-of-thought and before the actual tool call, providing transparency into the model's reasoning and enhancing debuggability, user confidence, and fine-grained steerability.

By letting GPT-5 “think out loud” before each tool call, preambles boost tool-calling accuracy (and overall task success) without bloating reasoning overhead. To enable preambles, add a system or developer instruction—for example: “Before you call a tool, explain why you are calling it.” GPT-5 prepends a concise rationale to each specified tool call. The model may also output multiple messages between tool calls, which can enhance the interaction experience—particularly for minimal reasoning or latency-sensitive use cases.

For more on using preambles, see the [GPT-5 prompting cookbook](https://cookbook.openai.com/examples/gpt-5/gpt-5_prompting_guide#tool-preambles).

Migration guidance
------------------

GPT-5 is our best model yet, and it works best with the Responses API, which supports for passing chain of thought (CoT) between turns. Read below to migrate from your current model or API.

### Migrating from other models to GPT-5

We see improved intelligence because the Responses API can pass the previous turn's CoT to the model. This leads to fewer generated reasoning tokens, higher cache hit rates, and less latency. To learn more, see an [in-depth guide](https://cookbook.openai.com/examples/responses_api/reasoning_items) on the benefits of responses.

When migrating to GPT-5 from an older OpenAI model, start by experimenting with reasoning levels and prompting strategies. Based on our testing, we recommend using our [prompt optimizer](http://platform.openai.com/chat/edit?optimize=true)—which automatically updates your prompts for GPT-5 based on our best practices—and following this model-specific guidance:

*   **o3**: `gpt-5` with `medium` or `high` reasoning is a great replacement. Start with `medium` reasoning with prompt tuning, then increasing to `high` if you aren't getting the results you want.
*   **gpt-4.1**: `gpt-5` with `minimal` or `low` reasoning is a strong alternative. Start with `minimal` and tune your prompts; increase to `low` if you need better performance.
*   **o4-mini or gpt-4.1-mini**: `gpt-5-mini` with prompt tuning is a great replacement.
*   **gpt-4.1-nano**: `gpt-5-nano` with prompt tuning is a great replacement.

### GPT-5 parameter compatibility

⚠️ **Important:** The following parameters are **not supported** when using GPT-5 models (e.g. `gpt-5`, `gpt-5-mini`, `gpt-5-nano`):

*   `temperature`
*   `top_p`
*   `logprobs`

Requests that include these fields will raise an error.

**Instead, use the following GPT-5-specific controls:**

*   **Reasoning depth:** `reasoning: { effort: "minimal" | "low" | "medium" | "high" }`
*   **Output verbosity:** `text: { verbosity: "low" | "medium" | "high" }`
*   **Output length:** `max_output_tokens`

### Migrating from Chat Completions to Responses API

The biggest difference, and main reason to migrate from Chat Completions to the Responses API for GPT-5, is support for passing chain of thought (CoT) between turns. See a full [comparison of the APIs](/docs/guides/responses-vs-chat-completions).

Passing CoT exists only in the Responses API, and we've seen improved intelligence, fewer generated reasoning tokens, higher cache hit rates, and lower latency as a result of doing so. Most other parameters remain at parity, though the formatting is different. Here's how new parameters are handled differently between Chat Completions and the Responses API:

**Reasoning effort**

Responses API

Generate response with minimal reasoning

```json
curl --request POST \
--url https://api.openai.com/v1/responses \
--header "Authorization: Bearer $OPENAI_API_KEY" \
--header 'Content-type: application/json' \
--data '{
  "model": "gpt-5",
  "input": "How much gold would it take to coat the Statue of Liberty in a 1mm layer?",
  "reasoning": {
    "effort": "minimal"
  }
}'
```

Chat Completions

Generate response with minimal reasoning

```json
curl --request POST \
--url https://api.openai.com/v1/chat/completions \
--header "Authorization: Bearer $OPENAI_API_KEY" \
--header 'Content-type: application/json' \
--data '{
  "model": "gpt-5",
  "messages": [
    {
      "role": "user",
      "content": "How much gold would it take to coat the Statue of Liberty in a 1mm layer?"
    }
  ],
  "reasoning_effort": "minimal"
}'
```

**Verbosity**

Responses API

Control verbosity

```json
curl --request POST \
--url https://api.openai.com/v1/responses \
--header "Authorization: Bearer $OPENAI_API_KEY" \
--header 'Content-type: application/json' \
--data '{
  "model": "gpt-5",
  "input": "What is the answer to the ultimate question of life, the universe, and everything?",
  "text": {
    "verbosity": "low"
  }
}'
```

Chat Completions

Control verbosity

```json
curl --request POST \
--url https://api.openai.com/v1/chat/completions \
--header "Authorization: Bearer $OPENAI_API_KEY" \
--header 'Content-type: application/json' \
--data '{
  "model": "gpt-5",
  "messages": [
    { "role": "user", "content": "What is the answer to the ultimate question of life, the universe, and everything?" }
  ],
  "verbosity": "low"
}'
```

**Custom tools**

Responses API

Custom tool call

```json
curl --request POST --url https://api.openai.com/v1/responses --header "Authorization: Bearer $OPENAI_API_KEY" --header 'Content-type: application/json' --data '{
  "model": "gpt-5",
  "input": "Use the code_exec tool to calculate the area of a circle with radius equal to the number of r letters in blueberry",
  "tools": [
    {
      "type": "custom",
      "name": "code_exec",
      "description": "Executes arbitrary python code"
    }
  ]
}'
```

Chat Completions

Custom tool call

```json
curl --request POST --url https://api.openai.com/v1/chat/completions --header "Authorization: Bearer $OPENAI_API_KEY" --header 'Content-type: application/json' --data '{
  "model": "gpt-5",
  "messages": [
    { "role": "user", "content": "Use the code_exec tool to calculate the area of a circle with radius equal to the number of r letters in blueberry" }
  ],
  "tools": [
    {
      "type": "custom",
      "custom": {
        "name": "code_exec",
        "description": "Executes arbitrary python code"
      }
    }
  ]
}'
```

Prompting guidance
------------------

We specifically designed GPT-5 to excel at coding, frontend engineering, and tool-calling for agentic tasks. We also recommend iterating on prompts for GPT-5 using the [prompt optimizer](/chat/edit?optimize=true).

[

GPT-5 prompt optimizer

Craft the perfect prompt for GPT-5 in the dashboard

](/chat/edit?optimize=true)[

GPT-5 prompting guide

Learn full best practices for prompting GPT-5 models

](https://cookbook.openai.com/examples/gpt-5/gpt-5_prompting_guide)[

Frontend prompting for GPT-5

See prompt samples specific to frontend development

](https://cookbook.openai.com/examples/gpt-5/gpt-5_frontend)

### GPT-5 is a reasoning model

Reasoning models like GPT-5 break problems down step by step, producing an internal chain of thought that encodes their reasoning. To maximize performance, pass these reasoning items back to the model: this avoids re-reasoning and keeps interactions closer to the model's training distribution. In multi-turn conversations, passing a `previous_response_id` automatically makes earlier reasoning items available. This is especially important when using tools—for example, when a function call requires an extra round trip. In these cases, either include them with `previous_response_id` or add them directly to `input`.

Learn more about reasoning models and how to get the most out of them in our [reasoning guide](/docs/guides/reasoning).

Further reading
---------------

[GPT-5 prompting guide](https://cookbook.openai.com/examples/gpt-5/gpt-5_prompting_guide)

[GPT-5 frontend guide](https://cookbook.openai.com/examples/gpt-5/gpt-5_frontend)

[GPT-5 new features guide](https://cookbook.openai.com/examples/gpt-5/gpt-5_new_params_and_tools)

[Cookbook on reasoning models](https://cookbook.openai.com/examples/responses_api/reasoning_items)

[Comparison of Responses API vs. Chat Completions](/docs/guides/migrate-to-responses)

FAQ
---

1.  **How are these models integrated into ChatGPT?**

    In ChatGPT, there are two models: `gpt-5-chat` and `gpt-5-thinking`. They offer reasoning and minimal-reasoning capabilities, with a routing layer that selects the best model based on the user's question. Users can also invoke reasoning directly through the ChatGPT UI.

2.  **Will these models be supported in Codex?**

    Yes, `gpt-5` will be available in Codex and Codex CLI.

3.  **How does GPT-5 compare to GPT-5-Codex?**

    [`GPT-5-Codex`](/docs/models/gpt-5-codex) was specifically designed for use in Codex. Unlike `GPT-5`, which is a general-purpose model, we recommend using GPT-5-Codex only for agentic coding tasks in Codex or Codex-like environments, and GPT-5 for use cases in other domains. GPT-5-Codex is only available in the Responses API and supports low, medium, and high `reasoning_efforts` and function calling, structured outputs, and the `web_search` tool.

4.  **What is the deprecation plan for previous models?**

    Any model deprecations will be posted on our [deprecations page](/docs/deprecations#page-top). We'll send advanced notice of any model deprecations.



Migrate to the Responses API
============================

The [Responses API](/docs/api-reference/responses) is our new API primitive, an evolution of [Chat Completions](/docs/api-reference/chat) which brings added simplicity and powerful agentic primitives to your integrations.

**While Chat Completions remains supported, Responses is recommended for all new projects.**

About the Responses API
-----------------------

The Responses API is a unified interface for building powerful, agent-like applications. It contains:

*   Built-in tools like [web search](/docs/guides/tools-web-search), [file search](/docs/guides/tools-file-search) , [computer use](/docs/guides/tools-computer-use), [code interpreter](/docs/guides/tools-code-interpreter), and [remote MCPs](/docs/guides/tools-remote-mcp).
*   Seamless multi-turn interactions that allow you to pass previous responses for higher accuracy reasoning results.
*   Native multimodal support for text and images.

Responses benefits
------------------

The Responses API contains several benefits over Chat Completions:

*   **Better performance**: Using reasoning models, like GPT-5, with Responses will result in better model intelligence when compared to Chat Completions. Our internal evals reveal a 3% improvement in SWE-bench with same prompt and setup.
*   **Agentic by default**: The Responses API is an agentic loop, allowing the model to call multiple tools, like `web_search`, `image_generation`, `file_search`, `code_interpreter`, remote MCP servers, as well as your own custom functions, within the span of one API request.
*   **Lower costs**: Results in lower costs due to improved cache utilization (40% to 80% improvement when compared to Chat Completions in internal tests).
*   **Stateful context**: Use `store: true` to maintain state from turn to turn, preserving reasoning and tool context from turn-to-turn.
*   **Flexible inputs**: Pass a string with input or a list of messages; use instructions for system-level guidance.
*   **Encrypted reasoning**: Opt-out of statefulness while still benefiting from advanced reasoning.
*   **Future-proof**: Future-proofed for upcoming models.

|Capabilities|Chat Completions API|Responses API|
|---|---|---|
|Text generation|||
|Audio||Coming soon|
|Vision|||
|Structured Outputs|||
|Function calling|||
|Web search|||
|File search|||
|Computer use|||
|Code interpreter|||
|MCP|||
|Image generation|||
|Reasoning summaries|||

### Examples

See how the Responses API compares to the Chat Completions API in specific scenarios.

#### Messages vs. Items

Both APIs make it easy to generate output from our models. The input to, and result of, a call to Chat completions is an array of _Messages_, while the Responses API uses _Items_. An Item is a union of many types, representing the range of possibilities of model actions. A `message` is a type of Item, as is a `function_call` or `function_call_output`. Unlike a Chat Completions Message, where many concerns are glued together into one object, Items are distinct from one another and better represent the basic unit of model context.

Additionally, Chat Completions can return multiple parallel generations as `choices`, using the `n` param. In Responses, we've removed this param, leaving only one generation.

Chat Completions API

```python
from openai import OpenAI
client = OpenAI()

completion = client.chat.completions.create(
  model="gpt-5",
  messages=[
      {
          "role": "user",
          "content": "Write a one-sentence bedtime story about a unicorn."
      }
  ]
)

print(completion.choices[0].message.content)
```

Responses API

```python
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
  model="gpt-5",
  input="Write a one-sentence bedtime story about a unicorn."
)

print(response.output_text)
```

When you get a response back from the Responses API, the fields differ slightly. Instead of a `message`, you receive a typed `response` object with its own `id`. Responses are stored by default. Chat completions are stored by default for new accounts. To disable storage when using either API, set `store: false`.

The objects you recieve back from these APIs will differ slightly. In Chat Completions, you receive an array of `choices`, each containing a `message`. In Responses, you receive an array of Items labled `output`.

Chat Completions API

```json
{
  "id": "chatcmpl-C9EDpkjH60VPPIB86j2zIhiR8kWiC",
  "object": "chat.completion",
  "created": 1756315657,
  "model": "gpt-5-2025-08-07",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Under a blanket of starlight, a sleepy unicorn tiptoed through moonlit meadows, gathering dreams like dew to tuck beneath its silver mane until morning.",
        "refusal": null,
        "annotations": []
      },
      "finish_reason": "stop"
    }
  ],
  ...
}
```

Responses API

```json
{
  "id": "resp_68af4030592c81938ec0a5fbab4a3e9f05438e46b5f69a3b",
  "object": "response",
  "created_at": 1756315696,
  "model": "gpt-5-2025-08-07",
  "output": [
    {
      "id": "rs_68af4030baa48193b0b43b4c2a176a1a05438e46b5f69a3b",
      "type": "reasoning",
      "content": [],
      "summary": []
    },
    {
      "id": "msg_68af40337e58819392e935fb404414d005438e46b5f69a3b",
      "type": "message",
      "status": "completed",
      "content": [
        {
          "type": "output_text",
          "annotations": [],
          "logprobs": [],
          "text": "Under a quilt of moonlight, a drowsy unicorn wandered through quiet meadows, brushing blossoms with her glowing horn so they sighed soft lullabies that carried every dreamer gently to sleep."
        }
      ],
      "role": "assistant"
    }
  ],
  ...
}
```

### Additional differences

*   Responses are stored by default. Chat completions are stored by default for new accounts. To disable storage in either API, set `store: false`.
*   [Reasoning](/docs/guides/reasoning) models have a richer experience in the Responses API with [improved tool usage](/docs/guides/reasoning#keeping-reasoning-items-in-context).
*   Structured Outputs API shape is different. Instead of `response_format`, use `text.format` in Responses. Learn more in the [Structured Outputs](/docs/guides/structured-outputs) guide.
*   The function-calling API shape is different, both for the function config on the request, and function calls sent back in the response. See the full difference in the [function calling guide](/docs/guides/function-calling).
*   The Responses SDK has an `output_text` helper, which the Chat Completions SDK does not have.
*   In Chat Completions, conversation state must be managed manually. The Responses API has compatibility with the Conversations API for persistent conversations, or the ability to pass a `previous_response_id` to easily chain Responses together.

Migrating from Chat Completions
-------------------------------

### 1\. Update generation endpoints

Start by updating your generation endpoints from `post /v1/chat/completions` to `post /v1/responses`.

If you are not using functions or multimodal inputs, then you're done! Simple message inputs are compatible from one API to the other:

Web search tool

```bash
INPUT='[
  { "role": "system", "content": "You are a helpful assistant." },
  { "role": "user", "content": "Hello!" }
]'

curl -s https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d "{
    \"model\": \"gpt-5\",
    \"messages\": $INPUT
  }"

curl -s https://api.openai.com/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d "{
    \"model\": \"gpt-5\",
    \"input\": $INPUT
  }"
```

```javascript
const context = [
  { role: 'system', content: 'You are a helpful assistant.' },
  { role: 'user', content: 'Hello!' }
];

const completion = await client.chat.completions.create({
  model: 'gpt-5',
  messages: messages
});

const response = await client.responses.create({
  model: "gpt-5",
  input: context
});
```

```python
context = [
  { "role": "system", "content": "You are a helpful assistant." },
  { "role": "user", "content": "Hello!" }
]

completion = client.chat.completions.create(
  model="gpt-5",
  messages=messages
)

response = client.responses.create(
  model="gpt-5",
  input=context
)
```

Chat Completions

With Chat Completions, you need to create an array of messages that specify different roles and content for each role.

Generate text from a model

```javascript
import OpenAI from 'openai';
const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const completion = await client.chat.completions.create({
  model: 'gpt-5',
  messages: [
    { 'role': 'system', 'content': 'You are a helpful assistant.' },
    { 'role': 'user', 'content': 'Hello!' }
  ]
});
console.log(completion.choices[0].message.content);
```

```python
from openai import OpenAI
client = OpenAI()

completion = client.chat.completions.create(
    model="gpt-5",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)
print(completion.choices[0].message.content)
```

```bash
curl https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
      "model": "gpt-5",
      "messages": [
          {"role": "system", "content": "You are a helpful assistant."},
          {"role": "user", "content": "Hello!"}
      ]
  }'
```

Responses

With Responses, you can separate instructions and input at the top-level. The API shape is similar to Chat Completions but has cleaner semantics.

Generate text from a model

```javascript
import OpenAI from 'openai';
const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const response = await client.responses.create({
  model: 'gpt-5',
  instructions: 'You are a helpful assistant.',
  input: 'Hello!'
});

console.log(response.output_text);
```

```python
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-5",
    instructions="You are a helpful assistant.",
    input="Hello!"
)
print(response.output_text)
```

```bash
curl https://api.openai.com/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
      "model": "gpt-5",
      "instructions": "You are a helpful assistant.",
      "input": "Hello!"
  }'
```

### 2\. Update item definitions

Chat Completions

With Chat Completions, you need to create an array of messages that specify different roles and content for each role.

Generate text from a model

```javascript
import OpenAI from 'openai';
const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const completion = await client.chat.completions.create({
  model: 'gpt-5',
  messages: [
    { 'role': 'system', 'content': 'You are a helpful assistant.' },
    { 'role': 'user', 'content': 'Hello!' }
  ]
});
console.log(completion.choices[0].message.content);
```

```python
from openai import OpenAI
client = OpenAI()

completion = client.chat.completions.create(
    model="gpt-5",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)
print(completion.choices[0].message.content)
```

```bash
curl https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
      "model": "gpt-5",
      "messages": [
          {"role": "system", "content": "You are a helpful assistant."},
          {"role": "user", "content": "Hello!"}
      ]
  }'
```

Responses

With Responses, you can separate instructions and input at the top-level. The API shape is similar to Chat Completions but has cleaner semantics.

Generate text from a model

```javascript
import OpenAI from 'openai';
const client = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

const response = await client.responses.create({
  model: 'gpt-5',
  instructions: 'You are a helpful assistant.',
  input: 'Hello!'
});

console.log(response.output_text);
```

```python
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-5",
    instructions="You are a helpful assistant.",
    input="Hello!"
)
print(response.output_text)
```

```bash
curl https://api.openai.com/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
      "model": "gpt-5",
      "instructions": "You are a helpful assistant.",
      "input": "Hello!"
  }'
```

### 3\. Update multi-turn conversations

If you have multi-turn conversations in your application, update your context logic.

Chat Completions

In Chat Completions, you have to store and manage context yourself.

Multi-turn conversation

```javascript
let messages = [
    { 'role': 'system', 'content': 'You are a helpful assistant.' },
    { 'role': 'user', 'content': 'What is the capital of France?' }
  ];
const res1 = await client.chat.completions.create({
  model: 'gpt-5',
  messages
});

messages = messages.concat([res1.choices[0].message]);
messages.push({ 'role': 'user', 'content': 'And its population?' });

const res2 = await client.chat.completions.create({
  model: 'gpt-5',
  messages
});
```

```python
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is the capital of France?"}
]
res1 = client.chat.completions.create(model="gpt-5", messages=messages)

messages += [res1.choices[0].message]
messages += [{"role": "user", "content": "And its population?"}]

res2 = client.chat.completions.create(model="gpt-5", messages=messages)
```

Responses

With responses, the pattern is similar, you can pass outputs from one response to the input of another.

Multi-turn conversation

```python
context = [
    { "role": "role", "content": "What is the capital of France?" }
]
res1 = client.responses.create(
    model="gpt-5",
    input=context,
)

// Append the first response’s output to context
context += res1.output

// Add the next user message
context += [
    { "role": "role", "content": "And it's population?" }
]

res2 = client.responses.create(
    model="gpt-5",
    input=context,
)
```

```javascript
let context = [
  { role: "role", content: "What is the capital of France?" }
];

const res1 = await client.responses.create({
  model: "gpt-5",
  input: context,
});

// Append the first response’s output to context
context = context.concat(res1.output);

// Add the next user message
context.push({ role: "role", content: "And its population?" });

const res2 = await client.responses.create({
  model: "gpt-5",
  input: context,
});
```

As a simplification, we've also built a way to simply reference inputs and outputs from a previous response by passing its id. You can use \`previous\_response\_id\` to form chains of responses that build upon one other or create forks in a history.

Multi-turn conversation

```javascript
const res1 = await client.responses.create({
  model: 'gpt-5',
  input: 'What is the capital of France?',
  store: true
});

const res2 = await client.responses.create({
  model: 'gpt-5',
  input: 'And its population?',
  previous_response_id: res1.id,
  store: true
});
```

```python
res1 = client.responses.create(
    model="gpt-5",
    input="What is the capital of France?",
    store=True
)

res2 = client.responses.create(
    model="gpt-5",
    input="And its population?",
    previous_response_id=res1.id,
    store=True
)
```

### 4\. Decide when to use statefulness

Some organizations—such as those with Zero Data Retention (ZDR) requirements—cannot use the Responses API in a stateful way due to compliance or data retention policies. To support these cases, OpenAI offers encrypted reasoning items, allowing you to keep your workflow stateless while still benefiting from reasoning items.

To disable statefulness, but still take advantage of reasoning:

*   set `store: false` in the [store field](/docs/api-reference/responses/create#responses_create-store)
*   add `["reasoning.encrypted_content"]` to the [include field](/docs/api-reference/responses/create#responses_create-include)

The API will then return an encrypted version of the reasoning tokens, which you can pass back in future requests just like regular reasoning items. For ZDR organizations, OpenAI enforces store=false automatically. When a request includes encrypted\_content, it is decrypted in-memory (never written to disk), used for generating the next response, and then securely discarded. Any new reasoning tokens are immediately encrypted and returned to you, ensuring no intermediate state is ever persisted.

### 5\. Update function definitions

There are two minor, but notable, differences in how functions are defined between Chat Completions and Responses.

1.  In Chat Completions, functions are defined using externally tagged polymorphism, whereas in Responses, they are internally-tagged.
2.  In Chat Completions, functions are non-strict by default, whereas in the Responses API, functions _are_ strict by default.

The Responses API function example on the right is functionally equivalent to the Chat Completions example on the left.

Chat Completions API

```javascript
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "Determine weather in my location",
    "strict": true,
    "parameters": {
      "type": "object",
      "properties": {
        "location": {
          "type": "string",
        },
      },
      "additionalProperties": false,
      "required": [
        "location",
        "unit"
      ]
    }
  }
}
```

Responses API

```javascript
{
  "type": "function",
  "name": "get_weather",
  "description": "Determine weather in my location",
  "parameters": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
      },
    },
    "additionalProperties": false,
    "required": [
      "location",
      "unit"
    ]
  }
}
```

#### Follow function-calling best practices

In Responses, tool calls and their outputs are two distinct types of Items that are correlated using a `call_id`. See the [tool calling docs](/docs/guides/function-calling#function-tool-example) for more detail on how function calling works in Responses.

### 6\. Update Structured Outputs definition

In the Responses API, defining structured outputs have moved from `response_format` to `text.format`:

Chat Completions

Structured Outputs

```bash
curl https://api.openai.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
  "model": "gpt-5",
  "messages": [
    {
      "role": "user",
      "content": "Jane, 54 years old",
    }
  ],
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "person",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "minLength": 1
          },
          "age": {
            "type": "number",
            "minimum": 0,
            "maximum": 130
          }
        },
        "required": [
          "name",
          "age"
        ],
        "additionalProperties": false
      }
    }
  },
  "verbosity": "medium",
  "reasoning_effort": "medium"
}'
```

```python
from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
  model="gpt-5",
  messages=[
    {
      "role": "user",
      "content": "Jane, 54 years old",
    }
  ],
  response_format={
    "type": "json_schema",
    "json_schema": {
      "name": "person",
      "strict": True,
      "schema": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "minLength": 1
          },
          "age": {
            "type": "number",
            "minimum": 0,
            "maximum": 130
          }
        },
        "required": [
          "name",
          "age"
        ],
        "additionalProperties": False
      }
    }
  },
  verbosity="medium",
  reasoning_effort="medium"
)
```

```javascript
const completion = await openai.chat.completions.create({
  model: "gpt-5",
  messages: [
    {
      "role": "user",
      "content": "Jane, 54 years old",
    }
  ],
  response_format: {
    type: "json_schema",
    json_schema: {
      name: "person",
      strict: true,
      schema: {
        type: "object",
        properties: {
          name: {
            type: "string",
            minLength: 1
          },
          age: {
            type: "number",
            minimum: 0,
            maximum: 130
          }
        },
        required: [
          name,
          age
        ],
        additionalProperties: false
      }
    }
  },
  verbosity: "medium",
  reasoning_effort: "medium"
});
```

Responses

Structured Outputs

```bash
curl https://api.openai.com/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
  "model": "gpt-5",
  "input": "Jane, 54 years old",
  "text": {
    "format": {
      "type": "json_schema",
      "name": "person",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "minLength": 1
          },
          "age": {
            "type": "number",
            "minimum": 0,
            "maximum": 130
          }
        },
        "required": [
          "name",
          "age"
        ],
        "additionalProperties": false
      }
    }
  }
}'
```

```python
response = client.responses.create(
  model="gpt-5",
  input="Jane, 54 years old",
  text={
    "format": {
      "type": "json_schema",
      "name": "person",
      "strict": True,
      "schema": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "minLength": 1
          },
          "age": {
            "type": "number",
            "minimum": 0,
            "maximum": 130
          }
        },
        "required": [
          "name",
          "age"
        ],
        "additionalProperties": False
      }
    }
  }
)
```

```javascript
const response = await openai.responses.create({
  model: "gpt-5",
  input: "Jane, 54 years old",
  text: {
    format: {
      type: "json_schema",
      name: "person",
      strict: true,
      schema: {
        type: "object",
        properties: {
          name: {
            type: "string",
            minLength: 1
          },
          age: {
            type: "number",
            minimum: 0,
            maximum: 130
          }
        },
        required: [
          name,
          age
        ],
        additionalProperties: false
      }
    },
  }
});
```

### 7\. Upgrade to native tools

If your application has use cases that would benefit from OpenAI's native [tools](/docs/guides/tools), you can update your tool calls to use OpenAI's tools out of the box.

Chat Completions

With Chat Completions, you cannot use OpenAI's tools natively and have to write your own.

Web search tool

```javascript
async function web_search(query) {
    const fetch = (await import('node-fetch')).default;
    const res = await fetch(`https://api.example.com/search?q=${query}`);
    const data = await res.json();
    return data.results;
}

const completion = await client.chat.completions.create({
  model: 'gpt-5',
  messages: [
    { role: 'system', content: 'You are a helpful assistant.' },
    { role: 'user', content: 'Who is the current president of France?' }
  ],
  functions: [
    {
      name: 'web_search',
      description: 'Search the web for information',
      parameters: {
        type: 'object',
        properties: { query: { type: 'string' } },
        required: ['query']
      }
    }
  ]
});
```

```python
import requests

def web_search(query):
    r = requests.get(f"https://api.example.com/search?q={query}")
    return r.json().get("results", [])

completion = client.chat.completions.create(
    model="gpt-5",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Who is the current president of France?"}
    ],
    functions=[
        {
            "name": "web_search",
            "description": "Search the web for information",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    ]
)
```

```bash
curl https://api.example.com/search \
  -G \
  --data-urlencode "q=your+search+term" \
  --data-urlencode "key=$SEARCH_API_KEY"
```

Responses

With Responses, you can simply specify the tools that you are interested in.

Web search tool

```javascript
const answer = await client.responses.create({
    model: 'gpt-5',
    input: 'Who is the current president of France?',
    tools: [{ type: 'web_search' }]
});

console.log(answer.output_text);
```

```python
answer = client.responses.create(
    model="gpt-5",
    input="Who is the current president of France?",
    tools=[{"type": "web_search_preview"}]
)

print(answer.output_text)
```

```bash
curl https://api.openai.com/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-5",
    "input": "Who is the current president of France?",
    "tools": [{"type": "web_search"}]
  }'
```

Incremental migration
---------------------

The Responses API is a superset of the Chat Completions API. The Chat Completions API will also continue to be supported. As such, you can incrementally adopt the Responses API if desired. You can migrate user flows who would benefit from improved reasoning models to the Responses API while keeping other flows on the Chat Completions API until you're ready for a full migration.

As a best practice, we encourage all users to migrate to the Responses API to take advantage of the latest features and improvements from OpenAI.

Assistants API
--------------

Based on developer feedback from the [Assistants API](/docs/api-reference/assistants) beta, we've incorporated key improvements into the Responses API to make it more flexible, faster, and easier to use. The Responses API represents the future direction for building agents on OpenAI.

We now have Assistant-like and Thread-like objects in the Responses API. Learn more in the [migration guide](/docs/guides/assistants/migration). As of August 26th, 2025, we're deprecating the Assistants API, with a sunset date of August 26, 2026.

Structured model outputs
========================

Ensure text responses from the model adhere to a JSON schema you define.

JSON is one of the most widely used formats in the world for applications to exchange data.

Structured Outputs is a feature that ensures the model will always generate responses that adhere to your supplied [JSON Schema](https://json-schema.org/overview/what-is-jsonschema), so you don't need to worry about the model omitting a required key, or hallucinating an invalid enum value.

Some benefits of Structured Outputs include:

1.  **Reliable type-safety:** No need to validate or retry incorrectly formatted responses
2.  **Explicit refusals:** Safety-based model refusals are now programmatically detectable
3.  **Simpler prompting:** No need for strongly worded prompts to achieve consistent formatting

In addition to supporting JSON Schema in the REST API, the OpenAI SDKs for [Python](https://github.com/openai/openai-python/blob/main/helpers.md#structured-outputs-parsing-helpers) and [JavaScript](https://github.com/openai/openai-node/blob/master/helpers.md#structured-outputs-parsing-helpers) also make it easy to define object schemas using [Pydantic](https://docs.pydantic.dev/latest/) and [Zod](https://zod.dev/) respectively. Below, you can see how to extract information from unstructured text that conforms to a schema defined in code.

Getting a structured response

```javascript
import OpenAI from "openai";
import { zodTextFormat } from "openai/helpers/zod";
import { z } from "zod";

const openai = new OpenAI();

const CalendarEvent = z.object({
  name: z.string(),
  date: z.string(),
  participants: z.array(z.string()),
});

const response = await openai.responses.parse({
  model: "gpt-4o-2024-08-06",
  input: [
    { role: "system", content: "Extract the event information." },
    {
      role: "user",
      content: "Alice and Bob are going to a science fair on Friday.",
    },
  ],
  text: {
    format: zodTextFormat(CalendarEvent, "event"),
  },
});

const event = response.output_parsed;
```

```python
from openai import OpenAI
from pydantic import BaseModel

client = OpenAI()

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

response = client.responses.parse(
    model="gpt-4o-2024-08-06",
    input=[
        {"role": "system", "content": "Extract the event information."},
        {
            "role": "user",
            "content": "Alice and Bob are going to a science fair on Friday.",
        },
    ],
    text_format=CalendarEvent,
)

event = response.output_parsed
```

### Supported models

Structured Outputs is available in our [latest large language models](/docs/models), starting with GPT-4o. Older models like `gpt-4-turbo` and earlier may use [JSON mode](/docs/guides/structured-outputs#json-mode) instead.

When to use Structured Outputs via function calling vs via text.format

--------------------------------------------------------------------------

Structured Outputs is available in two forms in the OpenAI API:

1.  When using [function calling](/docs/guides/function-calling)
2.  When using a `json_schema` response format

Function calling is useful when you are building an application that bridges the models and functionality of your application.

For example, you can give the model access to functions that query a database in order to build an AI assistant that can help users with their orders, or functions that can interact with the UI.

Conversely, Structured Outputs via `response_format` are more suitable when you want to indicate a structured schema for use when the model responds to the user, rather than when the model calls a tool.

For example, if you are building a math tutoring application, you might want the assistant to respond to your user using a specific JSON Schema so that you can generate a UI that displays different parts of the model's output in distinct ways.

Put simply:

*   If you are connecting the model to tools, functions, data, etc. in your system, then you should use function calling - If you want to structure the model's output when it responds to the user, then you should use a structured `text.format`

The remainder of this guide will focus on non-function calling use cases in the Responses API. To learn more about how to use Structured Outputs with function calling, check out the

[

Function Calling

](/docs/guides/function-calling#function-calling-with-structured-outputs)

guide.

### Structured Outputs vs JSON mode

Structured Outputs is the evolution of [JSON mode](/docs/guides/structured-outputs#json-mode). While both ensure valid JSON is produced, only Structured Outputs ensure schema adherence. Both Structured Outputs and JSON mode are supported in the Responses API, Chat Completions API, Assistants API, Fine-tuning API and Batch API.

We recommend always using Structured Outputs instead of JSON mode when possible.

However, Structured Outputs with `response_format: {type: "json_schema", ...}` is only supported with the `gpt-4o-mini`, `gpt-4o-mini-2024-07-18`, and `gpt-4o-2024-08-06` model snapshots and later.

||Structured Outputs|JSON Mode|
|---|---|---|
|Outputs valid JSON|Yes|Yes|
|Adheres to schema|Yes (see supported schemas)|No|
|Compatible models|gpt-4o-mini, gpt-4o-2024-08-06, and later|gpt-3.5-turbo, gpt-4-* and gpt-4o-* models|
|Enabling|text: { format: { type: "json_schema", "strict": true, "schema": ... } }|text: { format: { type: "json_object" } }|

Examples
--------

Chain of thought

### Chain of thought

You can ask the model to output an answer in a structured, step-by-step way, to guide the user through the solution.

Structured Outputs for chain-of-thought math tutoring

```javascript
import OpenAI from "openai";
import { zodTextFormat } from "openai/helpers/zod";
import { z } from "zod";

const openai = new OpenAI();

const Step = z.object({
  explanation: z.string(),
  output: z.string(),
});

const MathReasoning = z.object({
  steps: z.array(Step),
  final_answer: z.string(),
});

const response = await openai.responses.parse({
  model: "gpt-4o-2024-08-06",
  input: [
    {
      role: "system",
      content:
        "You are a helpful math tutor. Guide the user through the solution step by step.",
    },
    { role: "user", content: "how can I solve 8x + 7 = -23" },
  ],
  text: {
    format: zodTextFormat(MathReasoning, "math_reasoning"),
  },
});

const math_reasoning = response.output_parsed;
```

```python
from openai import OpenAI
from pydantic import BaseModel

client = OpenAI()

class Step(BaseModel):
    explanation: str
    output: str

class MathReasoning(BaseModel):
    steps: list[Step]
    final_answer: str

response = client.responses.parse(
    model="gpt-4o-2024-08-06",
    input=[
        {
            "role": "system",
            "content": "You are a helpful math tutor. Guide the user through the solution step by step.",
        },
        {"role": "user", "content": "how can I solve 8x + 7 = -23"},
    ],
    text_format=MathReasoning,
)

math_reasoning = response.output_parsed
```

```bash
curl https://api.openai.com/v1/responses \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-2024-08-06",
    "input": [
      {
        "role": "system",
        "content": "You are a helpful math tutor. Guide the user through the solution step by step."
      },
      {
        "role": "user",
        "content": "how can I solve 8x + 7 = -23"
      }
    ],
    "text": {
      "format": {
        "type": "json_schema",
        "name": "math_reasoning",
        "schema": {
          "type": "object",
          "properties": {
            "steps": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "explanation": { "type": "string" },
                  "output": { "type": "string" }
                },
                "required": ["explanation", "output"],
                "additionalProperties": false
              }
            },
            "final_answer": { "type": "string" }
          },
          "required": ["steps", "final_answer"],
          "additionalProperties": false
        },
        "strict": true
      }
    }
  }'
```

#### Example response

```json
{
  "steps": [
    {
      "explanation": "Start with the equation 8x + 7 = -23.",
      "output": "8x + 7 = -23"
    },
    {
      "explanation": "Subtract 7 from both sides to isolate the term with the variable.",
      "output": "8x = -23 - 7"
    },
    {
      "explanation": "Simplify the right side of the equation.",
      "output": "8x = -30"
    },
    {
      "explanation": "Divide both sides by 8 to solve for x.",
      "output": "x = -30 / 8"
    },
    {
      "explanation": "Simplify the fraction.",
      "output": "x = -15 / 4"
    }
  ],
  "final_answer": "x = -15 / 4"
}
```

Structured data extraction

### Structured data extraction

You can define structured fields to extract from unstructured input data, such as research papers.

Extracting data from research papers using Structured Outputs

```javascript
import OpenAI from "openai";
import { zodTextFormat } from "openai/helpers/zod";
import { z } from "zod";

const openai = new OpenAI();

const ResearchPaperExtraction = z.object({
  title: z.string(),
  authors: z.array(z.string()),
  abstract: z.string(),
  keywords: z.array(z.string()),
});

const response = await openai.responses.parse({
  model: "gpt-4o-2024-08-06",
  input: [
    {
      role: "system",
      content:
        "You are an expert at structured data extraction. You will be given unstructured text from a research paper and should convert it into the given structure.",
    },
    { role: "user", content: "..." },
  ],
  text: {
    format: zodTextFormat(ResearchPaperExtraction, "research_paper_extraction"),
  },
});

const research_paper = response.output_parsed;
```

```python
from openai import OpenAI
from pydantic import BaseModel

client = OpenAI()

class ResearchPaperExtraction(BaseModel):
    title: str
    authors: list[str]
    abstract: str
    keywords: list[str]

response = client.responses.parse(
    model="gpt-4o-2024-08-06",
    input=[
        {
            "role": "system",
            "content": "You are an expert at structured data extraction. You will be given unstructured text from a research paper and should convert it into the given structure.",
        },
        {"role": "user", "content": "..."},
    ],
    text_format=ResearchPaperExtraction,
)

research_paper = response.output_parsed
```

```bash
curl https://api.openai.com/v1/responses \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-2024-08-06",
    "input": [
      {
        "role": "system",
        "content": "You are an expert at structured data extraction. You will be given unstructured text from a research paper and should convert it into the given structure."
      },
      {
        "role": "user",
        "content": "..."
      }
    ],
    "text": {
      "format": {
        "type": "json_schema",
        "name": "research_paper_extraction",
        "schema": {
          "type": "object",
          "properties": {
            "title": { "type": "string" },
            "authors": {
              "type": "array",
              "items": { "type": "string" }
            },
            "abstract": { "type": "string" },
            "keywords": {
              "type": "array",
              "items": { "type": "string" }
            }
          },
          "required": ["title", "authors", "abstract", "keywords"],
          "additionalProperties": false
        },
        "strict": true
      }
    }
  }'
```

#### Example response

```json
{
  "title": "Application of Quantum Algorithms in Interstellar Navigation: A New Frontier",
  "authors": [
    "Dr. Stella Voyager",
    "Dr. Nova Star",
    "Dr. Lyra Hunter"
  ],
  "abstract": "This paper investigates the utilization of quantum algorithms to improve interstellar navigation systems. By leveraging quantum superposition and entanglement, our proposed navigation system can calculate optimal travel paths through space-time anomalies more efficiently than classical methods. Experimental simulations suggest a significant reduction in travel time and fuel consumption for interstellar missions.",
  "keywords": [
    "Quantum algorithms",
    "interstellar navigation",
    "space-time anomalies",
    "quantum superposition",
    "quantum entanglement",
    "space travel"
  ]
}
```

UI generation

### UI Generation

You can generate valid HTML by representing it as recursive data structures with constraints, like enums.

Generating HTML using Structured Outputs

```javascript
import OpenAI from "openai";
import { zodTextFormat } from "openai/helpers/zod";
import { z } from "zod";

const openai = new OpenAI();

const UI = z.lazy(() =>
  z.object({
    type: z.enum(["div", "button", "header", "section", "field", "form"]),
    label: z.string(),
    children: z.array(UI),
    attributes: z.array(
      z.object({
        name: z.string(),
        value: z.string(),
      })
    ),
  })
);

const response = await openai.responses.parse({
  model: "gpt-4o-2024-08-06",
  input: [
    {
      role: "system",
      content: "You are a UI generator AI. Convert the user input into a UI.",
    },
    {
      role: "user",
      content: "Make a User Profile Form",
    },
  ],
  text: {
    format: zodTextFormat(UI, "ui"),
  },
});

const ui = response.output_parsed;
```

```python
from enum import Enum
from typing import List

from openai import OpenAI
from pydantic import BaseModel

client = OpenAI()

class UIType(str, Enum):
    div = "div"
    button = "button"
    header = "header"
    section = "section"
    field = "field"
    form = "form"

class Attribute(BaseModel):
    name: str
    value: str

class UI(BaseModel):
    type: UIType
    label: str
    children: List["UI"]
    attributes: List[Attribute]

UI.model_rebuild()  # This is required to enable recursive types

class Response(BaseModel):
    ui: UI

response = client.responses.parse(
    model="gpt-4o-2024-08-06",
    input=[
        {
            "role": "system",
            "content": "You are a UI generator AI. Convert the user input into a UI.",
        },
        {"role": "user", "content": "Make a User Profile Form"},
    ],
    text_format=Response,
)

ui = response.output_parsed
```

```bash
curl https://api.openai.com/v1/responses \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-2024-08-06",
    "input": [
      {
        "role": "system",
        "content": "You are a UI generator AI. Convert the user input into a UI."
      },
      {
        "role": "user",
        "content": "Make a User Profile Form"
      }
    ],
    "text": {
      "format": {
        "type": "json_schema",
        "name": "ui",
        "description": "Dynamically generated UI",
        "schema": {
          "type": "object",
          "properties": {
            "type": {
              "type": "string",
              "description": "The type of the UI component",
              "enum": ["div", "button", "header", "section", "field", "form"]
            },
            "label": {
              "type": "string",
              "description": "The label of the UI component, used for buttons or form fields"
            },
            "children": {
              "type": "array",
              "description": "Nested UI components",
              "items": {"$ref": "#"}
            },
            "attributes": {
              "type": "array",
              "description": "Arbitrary attributes for the UI component, suitable for any element",
              "items": {
                "type": "object",
                "properties": {
                  "name": {
                    "type": "string",
                    "description": "The name of the attribute, for example onClick or className"
                  },
                  "value": {
                    "type": "string",
                    "description": "The value of the attribute"
                  }
                },
                "required": ["name", "value"],
                "additionalProperties": false
              }
            }
          },
          "required": ["type", "label", "children", "attributes"],
          "additionalProperties": false
        },
        "strict": true
      }
    }
  }'
```

#### Example response

```json
{
  "type": "form",
  "label": "User Profile Form",
  "children": [
    {
      "type": "div",
      "label": "",
      "children": [
        {
          "type": "field",
          "label": "First Name",
          "children": [],
          "attributes": [
            {
              "name": "type",
              "value": "text"
            },
            {
              "name": "name",
              "value": "firstName"
            },
            {
              "name": "placeholder",
              "value": "Enter your first name"
            }
          ]
        },
        {
          "type": "field",
          "label": "Last Name",
          "children": [],
          "attributes": [
            {
              "name": "type",
              "value": "text"
            },
            {
              "name": "name",
              "value": "lastName"
            },
            {
              "name": "placeholder",
              "value": "Enter your last name"
            }
          ]
        }
      ],
      "attributes": []
    },
    {
      "type": "button",
      "label": "Submit",
      "children": [],
      "attributes": [
        {
          "name": "type",
          "value": "submit"
        }
      ]
    }
  ],
  "attributes": [
    {
      "name": "method",
      "value": "post"
    },
    {
      "name": "action",
      "value": "/submit-profile"
    }
  ]
}
```

Moderation

### Moderation

You can classify inputs on multiple categories, which is a common way of doing moderation.

Moderation using Structured Outputs

```javascript
import OpenAI from "openai";
import { zodTextFormat } from "openai/helpers/zod";
import { z } from "zod";

const openai = new OpenAI();

const ContentCompliance = z.object({
  is_violating: z.boolean(),
  category: z.enum(["violence", "sexual", "self_harm"]).nullable(),
  explanation_if_violating: z.string().nullable(),
});

const response = await openai.responses.parse({
    model: "gpt-4o-2024-08-06",
    input: [
      {
        "role": "system",
        "content": "Determine if the user input violates specific guidelines and explain if they do."
      },
      {
        "role": "user",
        "content": "How do I prepare for a job interview?"
      }
    ],
    text: {
        format: zodTextFormat(ContentCompliance, "content_compliance"),
    },
});

const compliance = response.output_parsed;
```

```python
from enum import Enum
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel

client = OpenAI()

class Category(str, Enum):
    violence = "violence"
    sexual = "sexual"
    self_harm = "self_harm"

class ContentCompliance(BaseModel):
    is_violating: bool
    category: Optional[Category]
    explanation_if_violating: Optional[str]

response = client.responses.parse(
    model="gpt-4o-2024-08-06",
    input=[
        {
            "role": "system",
            "content": "Determine if the user input violates specific guidelines and explain if they do.",
        },
        {"role": "user", "content": "How do I prepare for a job interview?"},
    ],
    text_format=ContentCompliance,
)

compliance = response.output_parsed
```

```bash
curl https://api.openai.com/v1/responses \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-2024-08-06",
    "input": [
      {
        "role": "system",
        "content": "Determine if the user input violates specific guidelines and explain if they do."
      },
      {
        "role": "user",
        "content": "How do I prepare for a job interview?"
      }
    ],
    "text": {
      "format": {
        "type": "json_schema",
        "name": "content_compliance",
        "description": "Determines if content is violating specific moderation rules",
        "schema": {
          "type": "object",
          "properties": {
            "is_violating": {
              "type": "boolean",
              "description": "Indicates if the content is violating guidelines"
            },
            "category": {
              "type": ["string", "null"],
              "description": "Type of violation, if the content is violating guidelines. Null otherwise.",
              "enum": ["violence", "sexual", "self_harm"]
            },
            "explanation_if_violating": {
              "type": ["string", "null"],
              "description": "Explanation of why the content is violating"
            }
          },
          "required": ["is_violating", "category", "explanation_if_violating"],
          "additionalProperties": false
        },
        "strict": true
      }
    }
  }'
```

#### Example response

```json
{
  "is_violating": false,
  "category": null,
  "explanation_if_violating": null
}
```

How to use Structured Outputs with text.format
----------------------------------------------

Step 1: Define your schema

First you must design the JSON Schema that the model should be constrained to follow. See the [examples](/docs/guides/structured-outputs#examples) at the top of this guide for reference.

While Structured Outputs supports much of JSON Schema, some features are unavailable either for performance or technical reasons. See [here](/docs/guides/structured-outputs#supported-schemas) for more details.

#### Tips for your JSON Schema

To maximize the quality of model generations, we recommend the following:

*   Name keys clearly and intuitively
*   Create clear titles and descriptions for important keys in your structure
*   Create and use evals to determine the structure that works best for your use case

Step 2: Supply your schema in the API call

To use Structured Outputs, simply specify

```json
text: { format: { type: "json_schema", "strict": true, "schema": … } }
```

For example:

```python
response = client.responses.create(
    model="gpt-4o-2024-08-06",
    input=[
        {"role": "system", "content": "You are a helpful math tutor. Guide the user through the solution step by step."},
        {"role": "user", "content": "how can I solve 8x + 7 = -23"}
    ],
    text={
        "format": {
            "type": "json_schema",
            "name": "math_response",
            "schema": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "explanation": {"type": "string"},
                                "output": {"type": "string"}
                            },
                            "required": ["explanation", "output"],
                            "additionalProperties": False
                        }
                    },
                    "final_answer": {"type": "string"}
                },
                "required": ["steps", "final_answer"],
                "additionalProperties": False
            },
            "strict": True
        }
    }
)

print(response.output_text)
```

```javascript
const response = await openai.responses.create({
    model: "gpt-4o-2024-08-06",
    input: [
        { role: "system", content: "You are a helpful math tutor. Guide the user through the solution step by step." },
        { role: "user", content: "how can I solve 8x + 7 = -23" }
    ],
    text: {
        format: {
            type: "json_schema",
            name: "math_response",
            schema: {
                type: "object",
                properties: {
                    steps: {
                        type: "array",
                        items: {
                            type: "object",
                            properties: {
                                explanation: { type: "string" },
                                output: { type: "string" }
                            },
                            required: ["explanation", "output"],
                            additionalProperties: false
                        }
                    },
                    final_answer: { type: "string" }
                },
                required: ["steps", "final_answer"],
                additionalProperties: false
            },
            strict: true
        }
    }
});

console.log(response.output_text);
```

```bash
curl https://api.openai.com/v1/responses \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-2024-08-06",
    "input": [
      {
        "role": "system",
        "content": "You are a helpful math tutor. Guide the user through the solution step by step."
      },
      {
        "role": "user",
        "content": "how can I solve 8x + 7 = -23"
      }
    ],
    "text": {
      "format": {
        "type": "json_schema",
        "name": "math_response",
        "schema": {
          "type": "object",
          "properties": {
            "steps": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "explanation": { "type": "string" },
                  "output": { "type": "string" }
                },
                "required": ["explanation", "output"],
                "additionalProperties": false
              }
            },
            "final_answer": { "type": "string" }
          },
          "required": ["steps", "final_answer"],
          "additionalProperties": false
        },
        "strict": true
      }
    }
  }'
```

**Note:** the first request you make with any schema will have additional latency as our API processes the schema, but subsequent requests with the same schema will not have additional latency.

Step 3: Handle edge cases

In some cases, the model might not generate a valid response that matches the provided JSON schema.

This can happen in the case of a refusal, if the model refuses to answer for safety reasons, or if for example you reach a max tokens limit and the response is incomplete.

```javascript
try {
  const response = await openai.responses.create({
    model: "gpt-4o-2024-08-06",
    input: [{
        role: "system",
        content: "You are a helpful math tutor. Guide the user through the solution step by step.",
      },
      {
        role: "user",
        content: "how can I solve 8x + 7 = -23"
      },
    ],
    max_output_tokens: 50,
    text: {
      format: {
        type: "json_schema",
        name: "math_response",
        schema: {
          type: "object",
          properties: {
            steps: {
              type: "array",
              items: {
                type: "object",
                properties: {
                  explanation: {
                    type: "string"
                  },
                  output: {
                    type: "string"
                  },
                },
                required: ["explanation", "output"],
                additionalProperties: false,
              },
            },
            final_answer: {
              type: "string"
            },
          },
          required: ["steps", "final_answer"],
          additionalProperties: false,
        },
        strict: true,
      },
    }
  });

  if (response.status === "incomplete" && response.incomplete_details.reason === "max_output_tokens") {
    // Handle the case where the model did not return a complete response
    throw new Error("Incomplete response");
  }

  const math_response = response.output[0].content[0];

  if (math_response.type === "refusal") {
    // handle refusal
    console.log(math_response.refusal);
  } else if (math_response.type === "output_text") {
    console.log(math_response.text);
  } else {
    throw new Error("No response content");
  }
} catch (e) {
  // Handle edge cases
  console.error(e);
}
```

```python
try:
    response = client.responses.create(
        model="gpt-4o-2024-08-06",
        input=[
            {
                "role": "system",
                "content": "You are a helpful math tutor. Guide the user through the solution step by step.",
            },
            {"role": "user", "content": "how can I solve 8x + 7 = -23"},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "math_response",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "steps": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "explanation": {"type": "string"},
                                    "output": {"type": "string"},
                                },
                                "required": ["explanation", "output"],
                                "additionalProperties": False,
                            },
                        },
                        "final_answer": {"type": "string"},
                    },
                    "required": ["steps", "final_answer"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        },
    )
except Exception as e:
    # handle errors like finish_reason, refusal, content_filter, etc.
    pass
```

###

Refusals with Structured Outputs

When using Structured Outputs with user-generated input, OpenAI models may occasionally refuse to fulfill the request for safety reasons. Since a refusal does not necessarily follow the schema you have supplied in `response_format`, the API response will include a new field called `refusal` to indicate that the model refused to fulfill the request.

When the `refusal` property appears in your output object, you might present the refusal in your UI, or include conditional logic in code that consumes the response to handle the case of a refused request.

```python
class Step(BaseModel):
    explanation: str
    output: str

class MathReasoning(BaseModel):
steps: list[Step]
final_answer: str

completion = client.chat.completions.parse(
model="gpt-4o-2024-08-06",
messages=[
{"role": "system", "content": "You are a helpful math tutor. Guide the user through the solution step by step."},
{"role": "user", "content": "how can I solve 8x + 7 = -23"}
],
response_format=MathReasoning,
)

math_reasoning = completion.choices[0].message

# If the model refuses to respond, you will get a refusal message

if (math_reasoning.refusal):
print(math_reasoning.refusal)
else:
print(math_reasoning.parsed)
```

```javascript
const Step = z.object({
explanation: z.string(),
output: z.string(),
});

const MathReasoning = z.object({
steps: z.array(Step),
final_answer: z.string(),
});

const completion = await openai.chat.completions.parse({
model: "gpt-4o-2024-08-06",
messages: [
{ role: "system", content: "You are a helpful math tutor. Guide the user through the solution step by step." },
{ role: "user", content: "how can I solve 8x + 7 = -23" },
],
response_format: zodResponseFormat(MathReasoning, "math_reasoning"),
});

const math_reasoning = completion.choices[0].message

// If the model refuses to respond, you will get a refusal message
if (math_reasoning.refusal) {
console.log(math_reasoning.refusal);
} else {
console.log(math_reasoning.parsed);
}
```

The API response from a refusal will look something like this:

```json
{
  "id": "resp_1234567890",
  "object": "response",
  "created_at": 1721596428,
  "status": "completed",
  "error": null,
  "incomplete_details": null,
  "input": [],
  "instructions": null,
  "max_output_tokens": null,
  "model": "gpt-4o-2024-08-06",
  "output": [{
    "id": "msg_1234567890",
    "type": "message",
    "role": "assistant",
    "content": [
      {
        "type": "refusal",
        "refusal": "I'm sorry, I cannot assist with that request."
      }
    ]
  }],
  "usage": {
    "input_tokens": 81,
    "output_tokens": 11,
    "total_tokens": 92,
    "output_tokens_details": {
      "reasoning_tokens": 0,
    }
  },
}
```

###

Tips and best practices

#### Handling user-generated input

If your application is using user-generated input, make sure your prompt includes instructions on how to handle situations where the input cannot result in a valid response.

The model will always try to adhere to the provided schema, which can result in hallucinations if the input is completely unrelated to the schema.

You could include language in your prompt to specify that you want to return empty parameters, or a specific sentence, if the model detects that the input is incompatible with the task.

#### Handling mistakes

Structured Outputs can still contain mistakes. If you see mistakes, try adjusting your instructions, providing examples in the system instructions, or splitting tasks into simpler subtasks. Refer to the [prompt engineering guide](/docs/guides/prompt-engineering) for more guidance on how to tweak your inputs.

#### Avoid JSON schema divergence

To prevent your JSON Schema and corresponding types in your programming language from diverging, we strongly recommend using the native Pydantic/zod sdk support.

If you prefer to specify the JSON schema directly, you could add CI rules that flag when either the JSON schema or underlying data objects are edited, or add a CI step that auto-generates the JSON Schema from type definitions (or vice-versa).

Streaming
---------

You can use streaming to process model responses or function call arguments as they are being generated, and parse them as structured data.

That way, you don't have to wait for the entire response to complete before handling it. This is particularly useful if you would like to display JSON fields one by one, or handle function call arguments as soon as they are available.

We recommend relying on the SDKs to handle streaming with Structured Outputs.

```python
from typing import List

from openai import OpenAI
from pydantic import BaseModel

class EntitiesModel(BaseModel):
    attributes: List[str]
    colors: List[str]
    animals: List[str]

client = OpenAI()

with client.responses.stream(
    model="gpt-4.1",
    input=[
        {"role": "system", "content": "Extract entities from the input text"},
        {
            "role": "user",
            "content": "The quick brown fox jumps over the lazy dog with piercing blue eyes",
        },
    ],
    text_format=EntitiesModel,
) as stream:
    for event in stream:
        if event.type == "response.refusal.delta":
            print(event.delta, end="")
        elif event.type == "response.output_text.delta":
            print(event.delta, end="")
        elif event.type == "response.error":
            print(event.error, end="")
        elif event.type == "response.completed":
            print("Completed")
            # print(event.response.output)

    final_response = stream.get_final_response()
    print(final_response)
```

```javascript
import { OpenAI } from "openai";
import { zodTextFormat } from "openai/helpers/zod";
import { z } from "zod";

const EntitiesSchema = z.object({
  attributes: z.array(z.string()),
  colors: z.array(z.string()),
  animals: z.array(z.string()),
});

const openai = new OpenAI();
const stream = openai.responses
  .stream({
    model: "gpt-4.1",
    input: [
      { role: "user", content: "What's the weather like in Paris today?" },
    ],
    text: {
      format: zodTextFormat(EntitiesSchema, "entities"),
    },
  })
  .on("response.refusal.delta", (event) => {
    process.stdout.write(event.delta);
  })
  .on("response.output_text.delta", (event) => {
    process.stdout.write(event.delta);
  })
  .on("response.output_text.done", () => {
    process.stdout.write("\n");
  })
  .on("response.error", (event) => {
    console.error(event.error);
  });

const result = await stream.finalResponse();

console.log(result);
```

Supported schemas
-----------------

Structured Outputs supports a subset of the [JSON Schema](https://json-schema.org/docs) language.

#### Supported types

The following types are supported for Structured Outputs:

*   String
*   Number
*   Boolean
*   Integer
*   Object
*   Array
*   Enum
*   anyOf

#### Supported properties

In addition to specifying the type of a property, you can specify a selection of additional constraints:

**Supported `string` properties:**

*   `pattern` — A regular expression that the string must match.
*   `format` — Predefined formats for strings. Currently supported:
    *   `date-time`
    *   `time`
    *   `date`
    *   `duration`
    *   `email`
    *   `hostname`
    *   `ipv4`
    *   `ipv6`
    *   `uuid`

**Supported `number` properties:**

*   `multipleOf` — The number must be a multiple of this value.
*   `maximum` — The number must be less than or equal to this value.
*   `exclusiveMaximum` — The number must be less than this value.
*   `minimum` — The number must be greater than or equal to this value.
*   `exclusiveMinimum` — The number must be greater than this value.

**Supported `array` properties:**

*   `minItems` — The array must have at least this many items.
*   `maxItems` — The array must have at most this many items.

Here are some examples on how you can use these type restrictions:

String Restrictions

```json
{
    "name": "user_data",
    "strict": true,
    "schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "The name of the user"
            },
            "username": {
                "type": "string",
                "description": "The username of the user. Must start with @",
                "pattern": "^@[a-zA-Z0-9_]+$"
            },
            "email": {
                "type": "string",
                "description": "The email of the user",
                "format": "email"
            }
        },
        "additionalProperties": false,
        "required": [
            "name", "username", "email"
        ]
    }
}
```

Number Restrictions

```json
{
    "name": "weather_data",
    "strict": true,
    "schema": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The location to get the weather for"
            },
            "unit": {
                "type": ["string", "null"],
                "description": "The unit to return the temperature in",
                "enum": ["F", "C"]
            },
            "value": {
                "type": "number",
                "description": "The actual temperature value in the location",
                "minimum": -130,
                "maximum": 130
            }
        },
        "additionalProperties": false,
        "required": [
            "location", "unit", "value"
        ]
    }
}
```

Note these constraints are [not yet supported for fine-tuned models](/docs/guides/structured-outputs#some-type-specific-keywords-are-not-yet-supported).

#### Root objects must not be `anyOf` and must be an object

Note that the root level object of a schema must be an object, and not use `anyOf`. A pattern that appears in Zod (as one example) is using a discriminated union, which produces an `anyOf` at the top level. So code such as the following won't work:

```javascript
import { z } from 'zod';
import { zodResponseFormat } from 'openai/helpers/zod';

const BaseResponseSchema = z.object({/* ... */});
const UnsuccessfulResponseSchema = z.object({/* ... */});

const finalSchema = z.discriminatedUnion('status', [
BaseResponseSchema,
UnsuccessfulResponseSchema,
]);

// Invalid JSON Schema for Structured Outputs
const json = zodResponseFormat(finalSchema, 'final_schema');
```

#### All fields must be `required`

To use Structured Outputs, all fields or function parameters must be specified as `required`.

```json
{
    "name": "get_weather",
    "description": "Fetches the weather in the given location",
    "strict": true,
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The location to get the weather for"
            },
            "unit": {
                "type": "string",
                "description": "The unit to return the temperature in",
                "enum": ["F", "C"]
            }
        },
        "additionalProperties": false,
        "required": ["location", "unit"]
    }
}
```

Although all fields must be required (and the model will return a value for each parameter), it is possible to emulate an optional parameter by using a union type with `null`.

```json
{
    "name": "get_weather",
    "description": "Fetches the weather in the given location",
    "strict": true,
    "parameters": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The location to get the weather for"
            },
            "unit": {
                "type": ["string", "null"],
                "description": "The unit to return the temperature in",
                "enum": ["F", "C"]
            }
        },
        "additionalProperties": false,
        "required": [
            "location", "unit"
        ]
    }
}
```

#### Objects have limitations on nesting depth and size

A schema may have up to 5000 object properties total, with up to 10 levels of nesting.

#### Limitations on total string size

In a schema, total string length of all property names, definition names, enum values, and const values cannot exceed 120,000 characters.

#### Limitations on enum size

A schema may have up to 1000 enum values across all enum properties.

For a single enum property with string values, the total string length of all enum values cannot exceed 15,000 characters when there are more than 250 enum values.

#### `additionalProperties: false` must always be set in objects

`additionalProperties` controls whether it is allowable for an object to contain additional keys / values that were not defined in the JSON Schema.

Structured Outputs only supports generating specified keys / values, so we require developers to set `additionalProperties: false` to opt into Structured Outputs.

```json
{
    "name": "get_weather",
    "description": "Fetches the weather in the given location",
    "strict": true,
    "schema": {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "The location to get the weather for"
            },
            "unit": {
                "type": "string",
                "description": "The unit to return the temperature in",
                "enum": ["F", "C"]
            }
        },
        "additionalProperties": false,
        "required": [
            "location", "unit"
        ]
    }
}
```

#### Key ordering

When using Structured Outputs, outputs will be produced in the same order as the ordering of keys in the schema.

#### Some type-specific keywords are not yet supported

*   **Composition:** `allOf`, `not`, `dependentRequired`, `dependentSchemas`, `if`, `then`, `else`

For fine-tuned models, we additionally do not support the following:

*   **For strings:** `minLength`, `maxLength`, `pattern`, `format`
*   **For numbers:** `minimum`, `maximum`, `multipleOf`
*   **For objects:** `patternProperties`
*   **For arrays:** `minItems`, `maxItems`

If you turn on Structured Outputs by supplying `strict: true` and call the API with an unsupported JSON Schema, you will receive an error.

#### For `anyOf`, the nested schemas must each be a valid JSON Schema per this subset

Here's an example supported anyOf schema:

```json
{
    "type": "object",
    "properties": {
        "item": {
            "anyOf": [
                {
                    "type": "object",
                    "description": "The user object to insert into the database",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the user"
                        },
                        "age": {
                            "type": "number",
                            "description": "The age of the user"
                        }
                    },
                    "additionalProperties": false,
                    "required": [
                        "name",
                        "age"
                    ]
                },
                {
                    "type": "object",
                    "description": "The address object to insert into the database",
                    "properties": {
                        "number": {
                            "type": "string",
                            "description": "The number of the address. Eg. for 123 main st, this would be 123"
                        },
                        "street": {
                            "type": "string",
                            "description": "The street name. Eg. for 123 main st, this would be main st"
                        },
                        "city": {
                            "type": "string",
                            "description": "The city of the address"
                        }
                    },
                    "additionalProperties": false,
                    "required": [
                        "number",
                        "street",
                        "city"
                    ]
                }
            ]
        }
    },
    "additionalProperties": false,
    "required": [
        "item"
    ]
}
```

#### Definitions are supported

You can use definitions to define subschemas which are referenced throughout your schema. The following is a simple example.

```json
{
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "$ref": "#/$defs/step"
            }
        },
        "final_answer": {
            "type": "string"
        }
    },
    "$defs": {
        "step": {
            "type": "object",
            "properties": {
                "explanation": {
                    "type": "string"
                },
                "output": {
                    "type": "string"
                }
            },
            "required": [
                "explanation",
                "output"
            ],
            "additionalProperties": false
        }
    },
    "required": [
        "steps",
        "final_answer"
    ],
    "additionalProperties": false
}
```

#### Recursive schemas are supported

Sample recursive schema using `#` to indicate root recursion.

```json
{
    "name": "ui",
    "description": "Dynamically generated UI",
    "strict": true,
    "schema": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "description": "The type of the UI component",
                "enum": ["div", "button", "header", "section", "field", "form"]
            },
            "label": {
                "type": "string",
                "description": "The label of the UI component, used for buttons or form fields"
            },
            "children": {
                "type": "array",
                "description": "Nested UI components",
                "items": {
                    "$ref": "#"
                }
            },
            "attributes": {
                "type": "array",
                "description": "Arbitrary attributes for the UI component, suitable for any element",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the attribute, for example onClick or className"
                        },
                        "value": {
                            "type": "string",
                            "description": "The value of the attribute"
                        }
                    },
                    "additionalProperties": false,
                    "required": ["name", "value"]
                }
            }
        },
        "required": ["type", "label", "children", "attributes"],
        "additionalProperties": false
    }
}
```

Sample recursive schema using explicit recursion:

```json
{
    "type": "object",
    "properties": {
        "linked_list": {
            "$ref": "#/$defs/linked_list_node"
        }
    },
    "$defs": {
        "linked_list_node": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "number"
                },
                "next": {
                    "anyOf": [
                        {
                            "$ref": "#/$defs/linked_list_node"
                        },
                        {
                            "type": "null"
                        }
                    ]
                }
            },
            "additionalProperties": false,
            "required": [
                "next",
                "value"
            ]
        }
    },
    "additionalProperties": false,
    "required": [
        "linked_list"
    ]
}
```

JSON mode
---------

JSON mode is a more basic version of the Structured Outputs feature. While JSON mode ensures that model output is valid JSON, Structured Outputs reliably matches the model's output to the schema you specify. We recommend you use Structured Outputs if it is supported for your use case.

When JSON mode is turned on, the model's output is ensured to be valid JSON, except for in some edge cases that you should detect and handle appropriately.

To turn on JSON mode with the Responses API you can set the `text.format` to `{ "type": "json_object" }`. If you are using function calling, JSON mode is always turned on.

Important notes:

*   When using JSON mode, you must always instruct the model to produce JSON via some message in the conversation, for example via your system message. If you don't include an explicit instruction to generate JSON, the model may generate an unending stream of whitespace and the request may run continually until it reaches the token limit. To help ensure you don't forget, the API will throw an error if the string "JSON" does not appear somewhere in the context.
*   JSON mode will not guarantee the output matches any specific schema, only that it is valid and parses without errors. You should use Structured Outputs to ensure it matches your schema, or if that is not possible, you should use a validation library and potentially retries to ensure that the output matches your desired schema.
*   Your application must detect and handle the edge cases that can result in the model output not being a complete JSON object (see below)

Handling edge cases

```javascript
const we_did_not_specify_stop_tokens = true;

try {
  const response = await openai.responses.create({
    model: "gpt-3.5-turbo-0125",
    input: [
      {
        role: "system",
        content: "You are a helpful assistant designed to output JSON.",
      },
      { role: "user", content: "Who won the world series in 2020? Please respond in the format {winner: ...}" },
    ],
    text: { format: { type: "json_object" } },
  });

  // Check if the conversation was too long for the context window, resulting in incomplete JSON
  if (response.status === "incomplete" && response.incomplete_details.reason === "max_output_tokens") {
    // your code should handle this error case
  }

  // Check if the OpenAI safety system refused the request and generated a refusal instead
  if (response.output[0].content[0].type === "refusal") {
    // your code should handle this error case
    // In this case, the .content field will contain the explanation (if any) that the model generated for why it is refusing
    console.log(response.output[0].content[0].refusal)
  }

  // Check if the model's output included restricted content, so the generation of JSON was halted and may be partial
  if (response.status === "incomplete" && response.incomplete_details.reason === "content_filter") {
    // your code should handle this error case
  }

  if (response.status === "completed") {
    // In this case the model has either successfully finished generating the JSON object according to your schema, or the model generated one of the tokens you provided as a "stop token"

    if (we_did_not_specify_stop_tokens) {
      // If you didn't specify any stop tokens, then the generation is complete and the content key will contain the serialized JSON object
      // This will parse successfully and should now contain  {"winner": "Los Angeles Dodgers"}
      console.log(JSON.parse(response.output_text))
    } else {
      // Check if the response.output_text ends with one of your stop tokens and handle appropriately
    }
  }
} catch (e) {
  // Your code should handle errors here, for example a network error calling the API
  console.error(e)
}
```

```python
we_did_not_specify_stop_tokens = True

try:
    response = client.responses.create(
        model="gpt-3.5-turbo-0125",
        input=[
            {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
            {"role": "user", "content": "Who won the world series in 2020? Please respond in the format {winner: ...}"}
        ],
        text={"format": {"type": "json_object"}}
    )

    # Check if the conversation was too long for the context window, resulting in incomplete JSON
    if response.status == "incomplete" and response.incomplete_details.reason == "max_output_tokens":
        # your code should handle this error case
        pass

    # Check if the OpenAI safety system refused the request and generated a refusal instead
    if response.output[0].content[0].type == "refusal":
        # your code should handle this error case
        # In this case, the .content field will contain the explanation (if any) that the model generated for why it is refusing
        print(response.output[0].content[0]["refusal"])

    # Check if the model's output included restricted content, so the generation of JSON was halted and may be partial
    if response.status == "incomplete" and response.incomplete_details.reason == "content_filter":
        # your code should handle this error case
        pass

    if response.status == "completed":
        # In this case the model has either successfully finished generating the JSON object according to your schema, or the model generated one of the tokens you provided as a "stop token"

        if we_did_not_specify_stop_tokens:
            # If you didn't specify any stop tokens, then the generation is complete and the content key will contain the serialized JSON object
            # This will parse successfully and should now contain  "{"winner": "Los Angeles Dodgers"}"
            print(response.output_text)
        else:
            # Check if the response.output_text ends with one of your stop tokens and handle appropriately
            pass
except Exception as e:
    # Your code should handle errors here, for example a network error calling the API
    print(e)
```

Resources
---------

To learn more about Structured Outputs, we recommend browsing the following resources:

*   Check out our [introductory cookbook](https://cookbook.openai.com/examples/structured_outputs_intro) on Structured Outputs
*   Learn [how to build multi-agent systems](https://cookbook.openai.com/examples/structured_outputs_multi_agent) with Structured Outputs

File inputs
===========

Learn how to use PDF files as inputs to the OpenAI API.

OpenAI models with vision capabilities can also accept PDF files as input. Provide PDFs either as Base64-encoded data or as file IDs obtained after uploading files to the `/v1/files` endpoint through the [API](/docs/api-reference/files) or [dashboard](/storage/files/).

How it works
------------

To help models understand PDF content, we put into the model's context both the extracted text and an image of each page. The model can then use both the text and the images to generate a response. This is useful, for example, if diagrams contain key information that isn't in the text.

File URLs
---------

You can upload PDF file inputs by linking external URLs.

Link an external URL to a file to use in a response

```bash
curl "https://api.openai.com/v1/responses" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $OPENAI_API_KEY" \
    -d '{
        "model": "gpt-5",
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Analyze the letter and provide a summary of the key points."
                    },
                    {
                        "type": "input_file",
                        "file_url": "https://www.berkshirehathaway.com/letters/2024ltr.pdf"
                    }
                ]
            }
        ]
    }'
```

```javascript
import OpenAI from "openai";
const client = new OpenAI();

const response = await client.responses.create({
    model: "gpt-5",
    input: [
        {
            role: "user",
            content: [
                {
                    type: "input_text",
                    text: "Analyze the letter and provide a summary of the key points.",
                },
                {
                    type: "input_file",
                    file_url: "https://www.berkshirehathaway.com/letters/2024ltr.pdf",
                },
            ],
        },
    ],
});

console.log(response.output_text);
```

```python
from openai import OpenAI
client = OpenAI()

response = client.responses.create(
    model="gpt-5",
    input=[
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "Analyze the letter and provide a summary of the key points.",
                },
                {
                    "type": "input_file",
                    "file_url": "https://www.berkshirehathaway.com/letters/2024ltr.pdf",
                },
            ],
        },
    ]
)

print(response.output_text)
```

```csharp
using OpenAI.Files;
using OpenAI.Responses;

string key = Environment.GetEnvironmentVariable("OPENAI_API_KEY")!;
OpenAIResponseClient client = new(model: "gpt-5", apiKey: key);

using HttpClient http = new();
using Stream stream = await http.GetStreamAsync("https://www.berkshirehathaway.com/letters/2024ltr.pdf");
OpenAIFileClient files = new(key);
OpenAIFile file = files.UploadFile(stream, "2024ltr.pdf", FileUploadPurpose.UserData);

OpenAIResponse response = (OpenAIResponse)client.CreateResponse([
    ResponseItem.CreateUserMessageItem([
        ResponseContentPart.CreateInputTextPart("Analyze the letter and provide a summary of the key points."),
        ResponseContentPart.CreateInputFilePart(file.Id),
    ]),
]);

Console.WriteLine(response.GetOutputText());
```

Uploading files
---------------

In the example below, we first upload a PDF using the [Files API](/docs/api-reference/files), then reference its file ID in an API request to the model.

Upload a file to use in a response

```bash
curl https://api.openai.com/v1/files \
    -H "Authorization: Bearer $OPENAI_API_KEY" \
    -F purpose="user_data" \
    -F file="@draconomicon.pdf"

curl "https://api.openai.com/v1/responses" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $OPENAI_API_KEY" \
    -d '{
        "model": "gpt-5",
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "file_id": "file-6F2ksmvXxt4VdoqmHRw6kL"
                    },
                    {
                        "type": "input_text",
                        "text": "What is the first dragon in the book?"
                    }
                ]
            }
        ]
    }'
```

```javascript
import fs from "fs";
import OpenAI from "openai";
const client = new OpenAI();

const file = await client.files.create({
    file: fs.createReadStream("draconomicon.pdf"),
    purpose: "user_data",
});

const response = await client.responses.create({
    model: "gpt-5",
    input: [
        {
            role: "user",
            content: [
                {
                    type: "input_file",
                    file_id: file.id,
                },
                {
                    type: "input_text",
                    text: "What is the first dragon in the book?",
                },
            ],
        },
    ],
});

console.log(response.output_text);
```

```python
from openai import OpenAI
client = OpenAI()

file = client.files.create(
    file=open("draconomicon.pdf", "rb"),
    purpose="user_data"
)

response = client.responses.create(
    model="gpt-5",
    input=[
        {
            "role": "user",
            "content": [
                {
                    "type": "input_file",
                    "file_id": file.id,
                },
                {
                    "type": "input_text",
                    "text": "What is the first dragon in the book?",
                },
            ]
        }
    ]
)

print(response.output_text)
```

```csharp
using OpenAI.Files;
using OpenAI.Responses;

string key = Environment.GetEnvironmentVariable("OPENAI_API_KEY")!;
OpenAIResponseClient client = new(model: "gpt-5", apiKey: key);

OpenAIFileClient files = new(key);
OpenAIFile file = files.UploadFile("draconomicon.pdf", FileUploadPurpose.UserData);

OpenAIResponse response = (OpenAIResponse)client.CreateResponse([
    ResponseItem.CreateUserMessageItem([
        ResponseContentPart.CreateInputFilePart(file.Id),
        ResponseContentPart.CreateInputTextPart("What is the first dragon in the book?"),
    ]),
]);

Console.WriteLine(response.GetOutputText());
```

Base64-encoded files
--------------------

You can also send PDF file inputs as Base64-encoded inputs.

Base64 encode a file to use in a response

```bash
curl "https://api.openai.com/v1/responses" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $OPENAI_API_KEY" \
    -d '{
        "model": "gpt-5",
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "filename": "draconomicon.pdf",
                        "file_data": "...base64 encoded PDF bytes here..."
                    },
                    {
                        "type": "input_text",
                        "text": "What is the first dragon in the book?"
                    }
                ]
            }
        ]
    }'
```

```javascript
import fs from "fs";
import OpenAI from "openai";
const client = new OpenAI();

const data = fs.readFileSync("draconomicon.pdf");
const base64String = data.toString("base64");

const response = await client.responses.create({
    model: "gpt-5",
    input: [
        {
            role: "user",
            content: [
                {
                    type: "input_file",
                    filename: "draconomicon.pdf",
                    file_data: `data:application/pdf;base64,${base64String}`,
                },
                {
                    type: "input_text",
                    text: "What is the first dragon in the book?",
                },
            ],
        },
    ],
});

console.log(response.output_text);
```

```python
import base64
from openai import OpenAI
client = OpenAI()

with open("draconomicon.pdf", "rb") as f:
    data = f.read()

base64_string = base64.b64encode(data).decode("utf-8")

response = client.responses.create(
    model="gpt-5",
    input=[
        {
            "role": "user",
            "content": [
                {
                    "type": "input_file",
                    "filename": "draconomicon.pdf",
                    "file_data": f"data:application/pdf;base64,{base64_string}",
                },
                {
                    "type": "input_text",
                    "text": "What is the first dragon in the book?",
                },
            ],
        },
    ]
)

print(response.output_text)
```

Usage considerations
--------------------

Below are a few considerations to keep in mind while using PDF inputs.

**Token usage**

To help models understand PDF content, we put into the model's context both extracted text and an image of each page—regardless of whether the page includes images. Before deploying your solution at scale, ensure you understand the pricing and token usage implications of using PDFs as input. [More on pricing](/docs/pricing).

**File size limitations**

You can upload multiple files, each less than 10 MB. The total content limit across all files in a single API request is 32 MB.

**Supported models**

Only models that support both text and image inputs, such as gpt-4o, gpt-4o-mini, or o1, can accept PDF files as input. [Check model features here](/docs/models).

**File upload purpose**

You can upload these files to the Files API with any [purpose](/docs/api-reference/files/create#files-create-purpose), but we recommend using the `user_data` purpose for files you plan to use as model inputs.
