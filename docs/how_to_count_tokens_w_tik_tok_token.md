#!/usr/bin/env python
# coding: utf-8

# # How to count tokens with tiktoken
#
# [`tiktoken`](https://github.com/openai/tiktoken/blob/main/README.md) is a fast open-source tokenizer by OpenAI.
#
# Given a text string (e.g., `"tiktoken is great!"`) and an encoding (e.g., `"cl100k_base"`), a tokenizer can split the text string into a list of tokens (e.g., `["t", "ik", "token", " is", " great", "!"]`).
#
# Splitting text strings into tokens is useful because GPT models see text in the form of tokens. Knowing how many tokens are in a text string can tell you (a) whether the string is too long for a text model to process and (b) how much an OpenAI API call costs (as usage is priced by token).
#
#
# ## Encodings
#
# Encodings specify how text is converted into tokens. Different models use different encodings.
#
# `tiktoken` supports three encodings used by OpenAI models:
#
# | Encoding name           | OpenAI models                                       |
# |-------------------------|-----------------------------------------------------|
# | `o200k_base`            | `gpt-4o`, `gpt-4o-mini`                             |
# | `cl100k_base`           | `gpt-4-turbo`, `gpt-4`, `gpt-3.5-turbo`, `text-embedding-ada-002`, `text-embedding-3-small`, `text-embedding-3-large`  |
# | `p50k_base`             | Codex models, `text-davinci-002`, `text-davinci-003`|
# | `r50k_base` (or `gpt2`) | GPT-3 models like `davinci`                         |
#
# You can retrieve the encoding for a model using `tiktoken.encoding_for_model()` as follows:
# ```python
# encoding = tiktoken.encoding_for_model('gpt-4o-mini')
# ```
#
# Note that `p50k_base` overlaps substantially with `r50k_base`, and for non-code applications, they will usually give the same tokens.
#
# ## Tokenizer libraries by language
#
# For `o200k_base`, `cl100k_base` and `p50k_base` encodings:
# - Python: [tiktoken](https://github.com/openai/tiktoken/blob/main/README.md)
# - .NET / C#: [SharpToken](https://github.com/dmitry-brazhenko/SharpToken), [TiktokenSharp](https://github.com/aiqinxuancai/TiktokenSharp)
# - Java: [jtokkit](https://github.com/knuddelsgmbh/jtokkit)
# - Golang: [tiktoken-go](https://github.com/pkoukk/tiktoken-go)
# - Rust: [tiktoken-rs](https://github.com/zurawiki/tiktoken-rs)
#
# For `r50k_base` (`gpt2`) encodings, tokenizers are available in many languages.
# - Python: [tiktoken](https://github.com/openai/tiktoken/blob/main/README.md) (or alternatively [GPT2TokenizerFast](https://huggingface.co/docs/transformers/model_doc/gpt2#transformers.GPT2TokenizerFast))
# - JavaScript: [gpt-3-encoder](https://www.npmjs.com/package/gpt-3-encoder)
# - .NET / C#: [GPT Tokenizer](https://github.com/dluc/openai-tools)
# - Java: [gpt2-tokenizer-java](https://github.com/hyunwoongko/gpt2-tokenizer-java)
# - PHP: [GPT-3-Encoder-PHP](https://github.com/CodeRevolutionPlugins/GPT-3-Encoder-PHP)
# - Golang: [tiktoken-go](https://github.com/pkoukk/tiktoken-go)
# - Rust: [tiktoken-rs](https://github.com/zurawiki/tiktoken-rs)
#
# (OpenAI makes no endorsements or guarantees of third-party libraries.)
#
#
# ## How strings are typically tokenized
#
# In English, tokens commonly range in length from one character to one word (e.g., `"t"` or `" great"`), though in some languages tokens can be shorter than one character or longer than one word. Spaces are usually grouped with the starts of words (e.g., `" is"` instead of `"is "` or `" "`+`"is"`). You can quickly check how a string is tokenized at the [OpenAI Tokenizer](https://beta.openai.com/tokenizer), or the third-party [Tiktokenizer](https://tiktokenizer.vercel.app/) webapp.

# ## 0. Install `tiktoken`
#
# If needed, install `tiktoken` with `pip`:

# In[1]:


get_ipython().run_line_magic('pip', 'install --upgrade tiktoken -q')
get_ipython().run_line_magic('pip', 'install --upgrade openai -q')


# ## 1. Import `tiktoken`

# In[2]:


import tiktoken


# ## 2. Load an encoding
#
# Use `tiktoken.get_encoding()` to load an encoding by name.
#
# The first time this runs, it will require an internet connection to download. Later runs won't need an internet connection.

# In[3]:


encoding = tiktoken.get_encoding("cl100k_base")


# Use `tiktoken.encoding_for_model()` to automatically load the correct encoding for a given model name.

# In[4]:


encoding = tiktoken.encoding_for_model("gpt-4o-mini")


# ## 3. Turn text into tokens with `encoding.encode()`
#
#

# The `.encode()` method converts a text string into a list of token integers.

# In[5]:


encoding.encode("tiktoken is great!")


# Count tokens by counting the length of the list returned by `.encode()`.

# In[6]:


def num_tokens_from_string(string: str, encoding_name: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.get_encoding(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


# In[7]:


num_tokens_from_string("tiktoken is great!", "o200k_base")


# ## 4. Turn tokens into text with `encoding.decode()`

# `.decode()` converts a list of token integers to a string.

# In[8]:


encoding.decode([83, 8251, 2488, 382, 2212, 0])


# Warning: although `.decode()` can be applied to single tokens, beware that it can be lossy for tokens that aren't on utf-8 boundaries.

# For single tokens, `.decode_single_token_bytes()` safely converts a single integer token to the bytes it represents.

# In[9]:


[encoding.decode_single_token_bytes(token) for token in [83, 8251, 2488, 382, 2212, 0]]


# (The `b` in front of the strings indicates that the strings are byte strings.)

# ## 5. Comparing encodings
#
# Different encodings vary in how they split words, group spaces, and handle non-English characters. Using the methods above, we can compare different encodings on a few example strings.

# In[10]:


def compare_encodings(example_string: str) -> None:
    """Prints a comparison of three string encodings."""
    # print the example string
    print(f'\nExample string: "{example_string}"')
    # for each encoding, print the # of tokens, the token integers, and the token bytes
    for encoding_name in ["r50k_base", "p50k_base", "cl100k_base", "o200k_base"]:
        encoding = tiktoken.get_encoding(encoding_name)
        token_integers = encoding.encode(example_string)
        num_tokens = len(token_integers)
        token_bytes = [encoding.decode_single_token_bytes(token) for token in token_integers]
        print()
        print(f"{encoding_name}: {num_tokens} tokens")
        print(f"token integers: {token_integers}")
        print(f"token bytes: {token_bytes}")


# In[11]:


compare_encodings("antidisestablishmentarianism")


# In[12]:


compare_encodings("2 + 2 = 4")


# In[13]:


compare_encodings("お誕生日おめでとう")


# ## 6. Counting tokens for chat completions API calls
#
# ChatGPT models like `gpt-4o-mini` and `gpt-4` use tokens in the same way as older completions models, but because of their message-based formatting, it's more difficult to count how many tokens will be used by a conversation.
#
# Below is an example function for counting tokens for messages passed to `gpt-3.5-turbo`, `gpt-4`, `gpt-4o` and `gpt-4o-mini`.
#
# Note that the exact way that tokens are counted from messages may change from model to model. Consider the counts from the function below an estimate, not a timeless guarantee.
#
# In particular, requests that use the optional functions input will consume extra tokens on top of the estimates calculated below.

# In[14]:


def num_tokens_from_messages(messages, model="gpt-4o-mini-2024-07-18"):
    """Return the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using o200k_base encoding.")
        encoding = tiktoken.get_encoding("o200k_base")
    if model in {
        "gpt-3.5-turbo-0125",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
        "gpt-4o-mini-2024-07-18",
        "gpt-4o-2024-08-06"
        }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif "gpt-3.5-turbo" in model:
        print("Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0125.")
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0125")
    elif "gpt-4o-mini" in model:
        print("Warning: gpt-4o-mini may update over time. Returning num tokens assuming gpt-4o-mini-2024-07-18.")
        return num_tokens_from_messages(messages, model="gpt-4o-mini-2024-07-18")
    elif "gpt-4o" in model:
        print("Warning: gpt-4o and gpt-4o-mini may update over time. Returning num tokens assuming gpt-4o-2024-08-06.")
        return num_tokens_from_messages(messages, model="gpt-4o-2024-08-06")
    elif "gpt-4" in model:
        print("Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
        return num_tokens_from_messages(messages, model="gpt-4-0613")
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}."""
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


# In[15]:


# let's verify the function above matches the OpenAI API response

from openai import OpenAI
import os

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "<your OpenAI API key if not set as env var>"))

example_messages = [
    {
        "role": "system",
        "content": "You are a helpful, pattern-following assistant that translates corporate jargon into plain English.",
    },
    {
        "role": "system",
        "name": "example_user",
        "content": "New synergies will help drive top-line growth.",
    },
    {
        "role": "system",
        "name": "example_assistant",
        "content": "Things working well together will increase revenue.",
    },
    {
        "role": "system",
        "name": "example_user",
        "content": "Let's circle back when we have more bandwidth to touch base on opportunities for increased leverage.",
    },
    {
        "role": "system",
        "name": "example_assistant",
        "content": "Let's talk later when we're less busy about how to do better.",
    },
    {
        "role": "user",
        "content": "This late pivot means we don't have time to boil the ocean for the client deliverable.",
    },
]

for model in [
    "gpt-3.5-turbo",
    "gpt-4-0613",
    "gpt-4",
    "gpt-4o",
    "gpt-4o-mini"
    ]:
    print(model)
    # example token count from the function defined above
    print(f"{num_tokens_from_messages(example_messages, model)} prompt tokens counted by num_tokens_from_messages().")
    # example token count from the OpenAI API
    response = client.chat.completions.create(model=model,
    messages=example_messages,
    temperature=0,
    max_tokens=1)
    print(f'{response.usage.prompt_tokens} prompt tokens counted by the OpenAI API.')
    print()


# ## 7. Counting tokens for chat completions with tool calls
#
# Next, we will look into how to apply this calculations to messages that may contain function calls. This is not immediately trivial, due to the formatting of the tools themselves.
#
# Below is an example function for counting tokens for messages that contain tools, passed to `gpt-3.5-turbo`, `gpt-4`, `gpt-4o` and `gpt-4o-mini`.

# In[16]:


def num_tokens_for_tools(functions, messages, model):

    # Initialize function settings to 0
    func_init = 0
    prop_init = 0
    prop_key = 0
    enum_init = 0
    enum_item = 0
    func_end = 0

    if model in [
        "gpt-4o",
        "gpt-4o-mini"
    ]:

        # Set function settings for the above models
        func_init = 7
        prop_init = 3
        prop_key = 3
        enum_init = -3
        enum_item = 3
        func_end = 12
    elif model in [
        "gpt-3.5-turbo",
        "gpt-4"
    ]:
        # Set function settings for the above models
        func_init = 10
        prop_init = 3
        prop_key = 3
        enum_init = -3
        enum_item = 3
        func_end = 12
    else:
        raise NotImplementedError(
            f"""num_tokens_for_tools() is not implemented for model {model}."""
        )

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using o200k_base encoding.")
        encoding = tiktoken.get_encoding("o200k_base")

    func_token_count = 0
    if len(functions) > 0:
        for f in functions:
            func_token_count += func_init  # Add tokens for start of each function
            function = f["function"]
            f_name = function["name"]
            f_desc = function["description"]
            if f_desc.endswith("."):
                f_desc = f_desc[:-1]
            line = f_name + ":" + f_desc
            func_token_count += len(encoding.encode(line))  # Add tokens for set name and description
            if len(function["parameters"]["properties"]) > 0:
                func_token_count += prop_init  # Add tokens for start of each property
                for key in list(function["parameters"]["properties"].keys()):
                    func_token_count += prop_key  # Add tokens for each set property
                    p_name = key
                    p_type = function["parameters"]["properties"][key]["type"]
                    p_desc = function["parameters"]["properties"][key]["description"]
                    if "enum" in function["parameters"]["properties"][key].keys():
                        func_token_count += enum_init  # Add tokens if property has enum list
                        for item in function["parameters"]["properties"][key]["enum"]:
                            func_token_count += enum_item
                            func_token_count += len(encoding.encode(item))
                    if p_desc.endswith("."):
                        p_desc = p_desc[:-1]
                    line = f"{p_name}:{p_type}:{p_desc}"
                    func_token_count += len(encoding.encode(line))
        func_token_count += func_end

    messages_token_count = num_tokens_from_messages(messages, model)
    total_tokens = messages_token_count + func_token_count

    return total_tokens


# In[17]:


tools = [
  {
    "type": "function",
    "function": {
      "name": "get_current_weather",
      "description": "Get the current weather in a given location",
      "parameters": {
        "type": "object",
        "properties": {
          "location": {
            "type": "string",
            "description": "The city and state, e.g. San Francisco, CA",
          },
          "unit": {"type": "string",
                   "description": "The unit of temperature to return",
                   "enum": ["celsius", "fahrenheit"]},
        },
        "required": ["location"],
      },
    }
  }
]

example_messages = [
    {
        "role": "system",
        "content": "You are a helpful assistant that can answer to questions about the weather.",
    },
    {
        "role": "user",
        "content": "What's the weather like in San Francisco?",
    },
]

for model in [
    "gpt-3.5-turbo",
    "gpt-4",
    "gpt-4o",
    "gpt-4o-mini"
    ]:
    print(model)
    # example token count from the function defined above
    print(f"{num_tokens_for_tools(tools, example_messages, model)} prompt tokens counted by num_tokens_for_tools().")
    # example token count from the OpenAI API
    response = client.chat.completions.create(model=model,
          messages=example_messages,
          tools=tools,
          temperature=0)
    print(f'{response.usage.prompt_tokens} prompt tokens counted by the OpenAI API.')
    print()
