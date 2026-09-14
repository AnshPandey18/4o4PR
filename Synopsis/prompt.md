# 4o4PR PROJECT SYNOPSIS GENERATION PROMPT

## INITIAL CLARIFICATION PHASE

**Before generating any synopsis content, please answer the following questions. These will guide the generation of accurate, comprehensive sections:**

### 1. PROJECT STRUCTURE & TEAM
- [ ] Confirm: Are you submitting this as a **solo project** or with **team members**? If team, how many and should they be named?
- [ ] Supervisor name and current designation (Assistant Professor / Associate Professor / Professor)?
- [ ] **Exact project status**: Is the Bug Detector agent complete and ready? Has the Analysis agent been started? What's the current completion percentage (e.g., 40% - bug detector done, 60% remaining)?

### 2. TECHNICAL DEPTH
- [ ] For the **Bug Detector Agent**: 
  - What specific input formats does it accept (Python code snippets, files, AST structures)?
  - Which bug categories does it detect (syntax errors, logic errors, type mismatches, performance issues, security vulnerabilities)?
  - Does it use static analysis, AST parsing, pattern matching, or ML-based detection?
  
- [ ] For the **Analysis Agent** (upcoming):
  - Confirmed approach: Will it analyze structured JSON from bug detector?
  - Will it generate fix recommendations, severity rankings, or code patches?
  
- [ ] **Multi-agent coordination**: How do agents communicate (JSON handoff, shared state, event-driven)?

### 3. DIFFERENTIATION & RESEARCH GAP
- [ ] Existing single-agent solutions (e.g., linters, static analysis tools) you're comparing against?
- [ ] Key innovation: Is it the **multi-agent approach**, **reduced false positives**, **comprehensive debugging pipeline**, or something else?
- [ ] Any comparative performance metrics you're targeting (speed, accuracy, bug detection rate)?

### 4. TECH STACK CONFIRMATION
- [ ] Programming language: **Python only** or mixed?
- [ ] LLM frameworks: Are you using LangChain, CrewAI, Autogen, or custom orchestration?
- [ ] Any ML models for bug detection (BERT, CodeBERT, GPT-based)?
- [ ] Database: Will you persist bug reports/fixes (SQLite, PostgreSQL, or in-memory)?
- [ ] Testing framework: pytest, unittest, or other?

### 5. SCOPE & CONSTRAINTS
- [ ] Maximum project scope: Will 4o4PR handle **Python debugging only** or multiple languages (Java, JavaScript)?
- [ ] Code complexity limit: Single files, functions, or full project analysis?
- [ ] Intentional out-of-scope: (e.g., "No style suggestions, only functional bugs")?

### 6. EXPECTED OUTCOMES & METRICS
- [ ] Measurable success: (e.g., "Detect 95% of common bugs in < 2 seconds", "Reduce debugging time by 40%")?
- [ ] Demonstration plan: Live demo of bug detection on sample code?
- [ ] Performance benchmarks to measure (latency, accuracy, recall)?

### 7. TIMELINE & MILESTONES
- [ ] Project start date and expected completion date?
- [ ] Major milestones:
  - Bug detector refinement: __ weeks
  - Analysis agent development: __ weeks
  - Integration testing: __ weeks
  - Demo & documentation: __ weeks

### 8. REFERENCES & PRIOR ART
- [ ] Any papers on multi-agent debugging systems or LLM-based code analysis you're building on?
- [ ] Key tools/frameworks to cite (e.g., Pylint, Flake8, CodeBERT, existing multi-agent frameworks)?

---

## GENERATION PHASE

Once the above is answered, I will generate the synopsis **in the following chunks** to avoid token exhaustion:

### **CHUNK 1: Front Matter + Sections 1-3**
- Cover page details (title, students, supervisor)
- Table of Contents
- **Section 1: Abstract** (200-300 words + keywords)
- **Section 2: Introduction** (Background, Motivation, Need, Overview, Organization)
- **Section 3: Problem Statement, Objectives & Scope** (Problem, 4-5 objectives, scope, expected contribution)

### **CHUNK 2: Sections 4-5**
- **Section 4: Literature Survey** (3-5 paragraphs + matrix of 4-5 prior works)
- **Section 5: Research Gap & Proposed Solution** (Gap identification, existing systems, proposed advantages, comparison table)

### **CHUNK 3: Sections 6-7**
- **Section 6: Proposed Methodology / System Design** (Workflow, system architecture block diagram description, 6-step development plan)
- **Section 7: Technology Stack & Requirements** (Hardware table, software table, feasibility points)

### **CHUNK 4: Sections 8-10**
- **Section 8: Modules, Algorithms & Data Flow** (6 major modules table, key algorithm pseudocode, data flow/UML diagram description)
- **Section 9: Expected Results, Testing & Evaluation** (Expected results, testing strategy table, evaluation metrics)
- **Section 10: Conclusion & Future Scope** (Summary, future enhancements, relevance)

### **CHUNK 5: References + Final**
- **Section 11: References** (IEEE format, 8-10 relevant papers/tools)
- **Final Checklist**

---

## PROJECT CONTEXT FOR AI (Pre-filled Knowledge)

### Current 4o4PR State:
- **Architecture**: Multi-agent Python debugging system
- **Completed**: Bug Detector Agent (structured JSON output)
- **In Progress**: Analysis Agent
- **Planned**: Code fix suggestion agent (future)
- **Creator**: Smarth Gupta, 2nd-year B.Tech CSIT, Dronacharya Group of Institutions, Greater Noida
- **GitHub**: Musashiii03
- **Motivation**: Automate debugging via AI agents to reduce manual code review time and human error

### 4o4PR Key Features (Include in Synopsis):
1. **Modular agent architecture**: Each agent handles a specific debugging step
2. **Structured data pipeline**: JSON handoff between agents prevents information loss
3. **Extensibility**: New agents can be added without refactoring core
4. **Performance focus**: Designed to be faster than traditional static analyzers
5. **Comprehensive bug coverage**: Not just syntax, but logic and performance bugs

### Implied Novelty/Gap:
- Existing tools (Pylint, Flake8, SonarQube) are single-pass linters
- 4o4PR differs via: Multi-stage LLM-driven analysis, structured reasoning, context-aware recommendations
- This is a **research project**: Exploring whether multi-agent LLM orchestration improves debugging efficiency

---

## INSTRUCTIONS FOR RESPONSE

1. **First**, ask me the 8 clarification questions above (numbered 1-8). Wait for my answers.
2. **Then**, for each chunk:
   - Generate the exact content in the specified format
   - Use professional B.Tech project language
   - Include tables, lists, and structured content as shown in the template
   - Maintain consistency across sections
   - Provide placeholders only for diagrams (describe what should be inserted)
3. **Citation format**: IEEE only (as required by DGI)
4. **Tone**: Academic, formal, precise—appropriate for campus placement and industry review

---

## IMPORTANT NOTES

- **Do not** generate all sections in one response; follow the 5-chunk strategy.
- **Confirm** after each chunk before moving to the next.
- **Graphics/Diagrams**: Describe where they go; I'll create them separately or you can generate ASCII/SVG later.
- **Page numbering & formatting**: Will be handled when converting to the .docx template.
- Keep responses concise but complete—every section should be "ready to submit."

---

**Ready? Please answer the 8 clarification questions above, and I will begin with CHUNK 1 (Front Matter + Sections 1-3).**