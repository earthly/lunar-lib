@lunar-lib/ai-context/about-lunar.md:1  I wrote this file to explain at a high level how Lunar works.

Examples of real collectors and policies exist in @collectors and @policies .

Super rough examples of what our customers want to implement (and some notes of ours in bold) exist in @lunar-lib/ai-context/guardrails.md .

Can you spend some time researching the official Lunar documentation available in @docs  (see @lunar/docs/SUMMARY.md to orient yourself - it's like a TOC).

Summarize everything an AI would need to know to be able to write collectors and policies from scratch in a few markdown files, and put them in the folder @ai-context .

Things like the python SDK API, the types of collectors available, the format of the YAML, the general idea about how collectors and policies even work, the key concepts such as components and the component JSON.

Oh one more thing - in our marketing we use "guardrails" instead of "policies and collectors". You might not find that term in the docs - just wanted to give you a heads-up about that.

Spend as much time as you need on this task.

Feel free to amend @lunar-lib/ai-context/about-lunar.md if you feel like.

Let's break down the task in multiple steps:

1. Core concepts, general architecture, the way it works
2. Collector documentation
3. Come up with component JSON conventions. (These aren't documented - you need to invent some yourself)
4. Policy documentation

Let's start with task 1 only for now.