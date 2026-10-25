# Android Application Development Documentation Prompt

You are an expert Mobile Solutions Architect and Senior Android Developer. We have an existing web/backend system for our **Finance-Track/Management project**, and our next goal is to build a companion Android application.

**IMPORTANT: DO NOT create or write the actual Android application code.** Your sole task is to generate a highly detailed, comprehensive **documentation and development blueprint** that will serve as the master guide for an Android developer to start building the app from scratch.

Please analyze all existing connections, functionalities, and business logic in the current codebase and generate this documentation based on the following requirements. 

**Note:** If you have any doubts regarding the backend connections, architecture, or data flow at any point, please refer to the `Readme.md` file as your primary source of truth.

## 1. Complete System & Functionality Analysis
- **Current Capabilities:** Analyze and document every single functionality that currently exists in the project.
- **Backend & Data Connections:** Explain how the existing system's logic works under the hood. Detail the data models, database relationships, and exact API endpoints the Android application will need to interface with.

## 2. Pre-Development & Onboarding Guide
- **Prerequisites:** What must the developer know or set up *before* starting development? Mention required domain knowledge, SDK considerations, and environment configurations.
- **Tech Stack & Dependencies:** Suggest industry-standard Android libraries and architectures (e.g., Kotlin, MVVM/Clean Architecture, Jetpack Compose vs. XML, Retrofit, Room, Hilt/Dagger). **Crucially, ensure that all recommended libraries are robust and universally supported to avoid any dependency or compatibility issues across different mobile phones.**
- **File Architecture & Scaffolding:** Provide a detailed, structured guide on the exact file architecture. Explain how to initialize the project and organize the package/folder structure for scalable development.

## 3. Feature-by-Feature Implementation Strategy
- **Functionality Mapping:** For every feature identified in step 1, provide explicit instructions on how it should be implemented in the Android environment.
- **API & Integration:** How should the app communicate with the backend for each feature? Provide details on handling requests, responses, and network states.
- **Authentication & Security Issues:** Explain precisely how the Android app should handle user login, secure session/token storage (e.g., EncryptedSharedPreferences, Keystore), and sensitive financial data. Explicitly mention common security vulnerabilities to avoid while developing the app (e.g., insecure data storage, hardcoded API keys, MITM attacks).
- **Local Data & Caching:** Detail strategies for offline support or local data caching if applicable.

## 4. Development Considerations & Pitfalls
- **Gotchas:** Highlight any complex logic, edge cases, or specific quirks in the current backend that the Android developer must be aware of to prevent bugs.
- **Robust Error Handling:** Detail how the Android application should gracefully handle backend errors, network timeouts, and unexpected states. Error handling must be maintained exceptionally well throughout the app.
- **Common Development Issues:** At the end of the document, provide a dedicated list of common issues, roadblocks, or integration challenges that a developer might face during or after the development of the app and its backend integration.

## Execution Strategy
- **Parallel Analysis:** To fasten the process of analyzing the project and creating the resulting document, please spawn or create 3-4 sub-agents to perform tasks simultaneously.

## Output Requirements
- **Output File:** After your analysis, save the final documentation in a file named `Android-Development.md`.
- Structure your response as a detailed, professional, and production-ready Markdown document.
- Use clear headings, bullet points, and logically sequenced sections so a new developer can read it top-to-bottom and start coding immediately without confusion.
