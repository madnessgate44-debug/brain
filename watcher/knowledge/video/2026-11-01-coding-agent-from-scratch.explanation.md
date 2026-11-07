**1) What it is**
This is a video recording of a developer webinar introducing how to build AI coding agents from scratch, using open-source tools, function calling, and language models.

**2) Summary**
The presenter, Zan from the DevRel team at Together, hosts a webinar guiding participants through building a coding language model capable of searching, reading, running, and modifying code to solve open-ended tasks end-to-end. He begins with a quick introduction and a community raffle announcement before diving into the foundational building blocks of coding agents. The core of the session focuses on function calling, breaking down how a language model interacts with external tools through a multi-step request-and-response loop. Zan then introduces the essential tools a coding agent requires—such as reading files, listing directory contents, and editing files—and walks through code notebooks in real-time to demonstrate how the model executes these operations in a sandbox environment.

**3) Key points**
* [00:13] A live tweet was scheduled for a $100 credit pack raffle on the Together platform for users who engage by liking, retweeting, and commenting on the coding agents they build or use.
* [01:16] The webinar covers building a language model that can code, search, run, modify code, and solve open-ended tasks end-to-end like a software engineer or data scientist.
* [02:10] The three main building blocks of coding agents covered are function calling, retrieval and context, and code execution.
* [06:32] All code, guides, and blog posts mentioned in the talk are open-source and accessible via a provided link.
* [08:38] Function calling (or tool use) bridges the gap between language models and the real world, allowing models to invoke external tools when they lack fresh information or require specific capabilities.
* [10:31] Function calling operates in a five-step loop: the developer provides tools, the model outputs a tool request, the developer executes the tool, feeds the response back into the message history, and the model uses that context to answer the original prompt.
* [12:39] The bare essential tools a coding language model needs are the abilities to read files, edit files, and see existing files in its environment.
* [18:01] In the code walkthrough, Zan demonstrates a file-reading function, its schema description, and how the model requests it.
* [21:52] Additional tools are introduced to list files in a directory and edit files by specifying an old string and a new replacement string.

**4) Walkthrough**
* **Introduction & Raffle [00:00]:** Zan welcomes attendees, announces a Twitter raffle for a $100 credit pack on the Together platform, and encourages active questions in the chat.
* **Overview of Coding Agents [01:16]:** He outlines the goals of the session: explaining how language models can handle file I/O, code execution, codebase searching, and open-ended problem-solving.
* **The Concept of Function Calling [06:56]:** Zan explains limitations of standard text-in/text-out models (like outdated training cutoffs) and introduces tool calling as a mechanism to let models perform external actions.
* **The 5-Step Tool-Calling Loop [10:31]:** He breaks down the exact communication flow between the user/app and the language model when executing a tool call and feeding data back.
* **Essential Coding Tools [12:39]:** He identifies the core functions required for a coding agent: reading files, editing code, and listing directory files.
* **Live Code Notebook Walkthrough [17:42]:** Zan switches to a Google Colab notebook to demonstrate:
  * Defining a Python function to read files and structuring its schema with descriptive parameters.
  * Prompting the model to read a secret text file and capturing its tool call request.
  * Executing the file-reading function programmatically on the developer side and appending the output back into the model's message history.
  * Expanding the setup to include a directory-listing tool and an edit-file tool (which replaces an old string with a new string).
  * Letting the model create, save, and modify a Python script (like a FizzBuzz program) in a sandbox environment.

**5) Topics/keywords**
* Coding agents
* Function calling / Tool use
* Language models (LLMs)
* File I/O and code execution
* Software engineering automation
* Open-source AI
* Together platform
* Python programming and Google Colab

**6) Takeaways**
* Coding agents require more than basic text generation; they need external tools to interact with file systems and execute code.
* Function calling is not magical; it is a structured loop where the model requests a specific tool payload, the application executes it locally, and the result is fed back into the model's chat history.
* Essential tools for any coding agent include file readers, file editors, and directory listers.
* Sandboxed environments are crucial when letting AI agents execute code or modify files to prevent irreversible errors or data loss.