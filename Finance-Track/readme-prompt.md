# Comprehensive Codebase Analysis and Architecture Documentation Prompt

You are an expert Software Architect and Senior Backend/Frontend Developer. I need you to perform a deep, exhaustive, file-by-file analysis of this entire codebase. This is a **Finance-Track/Management project intended for personal use**. 

Your ultimate goal is to generate a highly detailed, production-grade `Readme.md` file that explains the project from A to Z. An external developer reading your documentation should be able to fully understand the system's logic, connections, and architecture without prior knowledge of the codebase.

**Key Scenario:** If a developer wants to build a companion mobile application (e.g., an Android app) for this project, your documentation must clearly detail all existing functionalities, API endpoints, data models, authentication mechanisms, and how everything is invoked within the current system so they know exactly how to integrate or replicate it natively.

Please carefully follow these exhaustive instructions and generate the final output as a proper `Readme.md`.

## 1. High-Level Overview & Tech Stack
- **Project Purpose:** Provide a clear summary of what the application does, its core features, and its intended use case.
- **Technology Stack:** List all languages, frameworks, libraries, and tools used in the project.
- **Directory Structure:** Map out the high-level folder structure and briefly explain the purpose of each directory.

## 2. Exhaustive File-by-File Breakdown
Analyze every single file in the codebase. For each file, document:
- **Purpose:** What does this file do and why does it exist?
- **Core Functions/Classes:** List the main functions, classes, or components defined in the file. Explain their logic, inputs, and outputs.
- **Business Logic:** Explain the specific business rules enforced in this file.
- **State & Storage:** How is data managed, modified, or persisted here?

## 3. Component Connections & Relationships
- **Inter-file Dependencies:** Analyze and document how files depend on and invoke each other. 
- **Module Integration:** Explain how different layers (e.g., routing, database models, utilities, UI components) communicate. 
- **Data Flow:** Detail how data objects travel between the presentation layer, controllers/services, and the database.

## 4. Architecture & Application Flow
- **Architecture Diagram:** Create a detailed architecture diagram using **Mermaid.js** syntax representing the high-level system architecture.
- **Sequence Diagrams:** Provide Mermaid.js sequence diagrams for critical user journeys (e.g., User Authentication, Adding a Finance Transaction, Generating a Report).
- **Database Schema (ERD):** Provide an Entity-Relationship Diagram (using Mermaid.js) detailing all tables/collections, relationships, and key fields.
- **Execution Flow:** Describe the step-by-step lifecycle of a request from user interaction to database execution and response.

## 5. API & Integration Details (Crucial for Mobile/Android Devs)
- **API Endpoints:** Document all available routes/endpoints, including HTTP methods, URL paths, required headers, and expected payloads.
- **Response Formats:** Provide examples of success and error JSON responses.
- **Authentication/Security:** Explain in detail how security is handled (e.g., sessions, tokens). How should an external mobile app authenticate?
- **Error Handling:** Detail the standard error formats and HTTP status codes returned by the system.

## Execution Strategy
- **Parallel Processing:** To ensure efficiency and speed, please spawn or start a sufficient number of sub-agents to process multiple files, directories, or analysis tasks simultaneously.

## 6. Output Formatting Requirements
- Present all of the above information beautifully formatted in Markdown.
- Ensure the final output is cohesive and structured as a complete `Readme.md`.
- Use clear heading hierarchies, bullet points, and code blocks for examples.
- Ensure all Mermaid diagrams are enclosed in properly formatted ```mermaid code blocks.
