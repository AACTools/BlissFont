# **Blissymbolics Digitization Project**

## **Technical Working Brief & Agent Execution Roadmap (2026 Edition)**

This document serves as the master specification, JSON schema definition, and step-by-step task list for an agentic coding workflow. It acts as the direct system prompt and bounding framework for your AI agents (Data Generation, Font Automation, and Full-Stack App Agents) to coordinate with human specialists.

## **1\. Project Overview & 2025/2026 Data Foundation Strategy**

The primary constraint of the Blissymbolics system is solved. Rather than compiling historic vector designs or guessing stroke pathways, this project leverages the **BCI Authorized Vocabulary of Blissymbolics (BCI-AV) 2025-02-15 Release** containing **6,183 active symbols**.

### **Targeted Real-World Data URLs (To be scraped by agents)**

* **Metadata & Translating Map:**  
  http://www.blissymbolics.net/BCI-AV\_2025-02-15/BCI-AV\_SKOG\_2025-02-15\_ID\_to\_gloss\_map.txt  
* **Vector Glyphs (Mapped by ID):**  
  http://www.blissymbolics.net/BCI-AV\_2025-02-15/bliss\_svg\_id.zip  
* **Semantic Derivations & Translations (20+ Languages):**  
  http://www.blissymbolics.net/BCI-AV\_2025-02-15/BCI-AV\_SKOG\_2025-02-15\_(en+sv+no+fi+hu+de+nl+af+ru+is+lt+lv+po+fr+es+pt+it+dk)+derivations\_8483-29642.xlsx  
* **Unicode Mapping Specs:** ISO/IEC JTC1/SC2/WG2 N5228 (Document L2/23-138) mapping spacing characters and combining diacritical marks.

## **2\. Agent Ingestion & Data Parsing Pipeline**

The **Data Generation Agent** is instructed to run an automated ETL (Extract, Transform, Load) pipeline executing these exact operations:

\[ Step 1: Download Archives \]  
    ├── Download bliss\_svg\_id.zip  
    └── Download Translations Excel & ID Gloss Map Text  
                 │  
                 ▼  
\[ Step 2: Extract & Sanitize SVG \]  
    ├── Unzip SVG vectors  
    └── Strip non-standard XML, namespaces, canvas sizes, and CSS (Clean inline elements)  
                 │  
                 ▼  
\[ Step 3: Parse Metadata & Relational Database \]  
    ├── Read BCI ID mappings and parse Excel Translations/Derivations  
    └── Generate unified SQLite/JSON mapping: ID \-\> SVG Path \-\> Lexical Translation  
                 │  
                 ▼  
\[ Step 4: Map Proposed Unicode \]  
    └── Cross-reference the 1,425 base characters of L2/23-138 and assign Unicode scalar blocks

## **3\. Core Agent Knowledge Graph: Structured JSON Schema**

All agents in this ecosystem must read, update, and adhere to this unified JSON schema. It bridges raw vector math, multi-language dictionaries, and proposed Unicode points.

{  
  "$schema": "http://json-schema.org/draft-07/schema\#",  
  "title": "BlissCharacterData",  
  "type": "object",  
  "required": \["bci\_id", "proposed\_unicode", "glosses", "category", "geometry", "anchors", "input\_method"\],  
  "properties": {  
    "bci\_id": {  
      "type": "string",  
      "description": "Primary ID from BCI-AV 2025 (e.g., '12054' or 'eye')"  
    },  
    "proposed\_unicode": {  
      "type": "string",  
      "pattern": "^(U\\\\+\[0-9A-F\]{4,5}|null)$",  
      "description": "Proposed Unicode scalar value under L2/23-138, or null if custom compound"  
    },  
    "glosses": {  
      "type": "object",  
      "description": "Glossary mappings scraped from BCI-AV 2025 Excel spreadsheet",  
      "properties": {  
        "en": { "type": "string" },  
        "sv": { "type": "string" },  
        "de": { "type": "string" },  
        "fr": { "type": "string" },  
        "nl": { "type": "string" }  
      }  
    },  
    "derivations": {  
      "type": "array",  
      "items": { "type": "string" },  
      "description": "Derivation formula components (e.g. \['man', 'machine'\])"  
    },  
    "category": {  
      "type": "string",  
      "enum": \["Base Spacing", "Indicator", "Punctuation", "Format Control", "Compound"\]  
    },  
    "geometry": {  
      "type": "object",  
      "required": \["stroke\_paths", "matrix\_metrics"\],  
      "properties": {  
        "stroke\_paths": {  
          "type": "array",  
          "items": { "type": "string" },  
          "description": "Raw extracted and cleaned SVG path definitions"  
        },  
        "matrix\_metrics": {  
          "type": "object",  
          "required": \["skyline", "midline", "earthline", "base\_width"\],  
          "properties": {  
            "skyline": { "type": "number", "description": "Y-coordinate for top boundaries" },  
            "midline": { "type": "number", "description": "Y-coordinate for central elements" },  
            "earthline": { "type": "number", "description": "Y-coordinate for bottom boundaries" },  
            "base\_width": { "type": "number" }  
          }  
        }  
      }  
    },  
    "anchors": {  
      "type": "object",  
      "required": \["top\_diacritic", "bottom\_diacritic"\],  
      "properties": {  
        "top\_diacritic": {  
          "type": "object",  
          "required": \["x", "y"\],  
          "properties": {  
            "x": { "type": "number" },  
            "y": { "type": "number" }  
          }  
        },  
        "bottom\_diacritic": {  
          "type": "object",  
          "required": \["x", "y"\],  
          "properties": {  
            "x": { "type": "number" },  
            "y": { "type": "number" }  
          }  
        }  
      }  
    },  
    "input\_method": {  
      "type": "object",  
      "required": \["primary\_key", "subordinate\_path"\],  
      "properties": {  
        "primary\_key": { "type": "string", "maxLength": 1, "description": "One of Everson's 29 core layout keys" },  
        "subordinate\_path": {  
          "type": "array",  
          "items": { "type": "string" },  
          "description": "Hierarchical tags derived from dictionary classifications"  
        }  
      }  
    }  
  }  
}

## **4\. Work Package Execution Blueprints**

### **🟢 Work Package 1: The Unicode Datafile (Unibliss)**

**Objective:** Programmatic compilation of the definitive Unibliss.txt character property dataset mapped against the 2025 release.

* **Task 1.1: Web Scraping and Ingestion**  
  * *Agent Action:* Auto-download the ZIP and Excel files listed in Section 1\. Extract, sanitize, and validate consistency between the SVG IDs and Excel IDs.  
* **Task 1.2: Digital Sorting & Relational Weights**  
  * *Agent Action:* Read semantic composition strings (from Excel column "derivations"). Formulate sorting weights where characters sharing radical components are grouped in adjacent index spaces.  
* **Task 1.3: Generate Unicode Output**  
  * *Agent Action:* Run a validator asserting strict conformity to the Standard Unicode character property file formats.

### **🟢 Work Package 2: Font Engineering & OpenType Smart Rules**

**Objective:** Generation of a fully responsive .otf / .woff2 font containing complex diacritic anchors and contextual layout tables.

* **Task 2.1: Automatic Vector Normalization**  
  * *Agent Action:* Write a script using defcon and fontTools to parse the 6,183 cleaned SVG graphics, scale them to standard UPM (Units Per Em, e.g., 1000), and generate unified font glyph contours.  
* **Task 2.2: OpenType Glyph Positioning (GPOS) Engine Injection**  
  * *Agent Action:* Parse output from the **Human Calibration & Review Tool** containing exact coordinate variables. Automatically inject Mark-to-Base lookup tables into the font header.  
* **Task 2.3: Contextual Substitution (GSUB) for Mirrored Layouts**  
  * *Agent Action:* Write a .fea layout script mirroring directional glyph structural nodes (e.g. indicators pointing in opposite directions in LTR vs RTL).

### **🟢 Work Package 3: Cross-Platform Input Method Schema (RIME Engine)**

**Objective:** Deploy a highly responsive, accessible, cross-platform input method using the open-source RIME Engine architecture, eliminating the need for a custom desktop application.

* **Task 3.1: Programmatic Translation Schema & Dictionary Generation**  
  * *Agent Action:* Parse the unified sqlite/JSON database generated in WP1. Automatically generate a structured RIME dictionary (blissymbols.dict.yaml) mapping Everson’s 29 physical key codes to the candidate list of 6,183 Bliss characters and translations.  
  * *Logic:* Ensure chorded combinations and semantic hierarchies are indexed correctly to return relevant candidate results.  
* **Task 3.2: RIME Blueprint Configuration (blissymbols.schema.yaml)**  
  * *Agent Action:* Write a declarative YAML schema detailing layout properties:  
    * Set key boundaries to bind only to the 29 designated Everson keys.  
    * Establish page-size candidates, search matching rules, and translation triggers.  
    * Inject custom segmenters and transliterators so users can optionally type English/local gloss names to locate symbols in the predictive menu.  
* **Task 3.3: Accessibility Tuning & Distribution Packages**  
  * *Agent Action:* Construct OS-specific distribution packages using standard RIME engine platforms: **Weasel** (Windows), **Squirrel** (macOS), and **ibus-rime** (Linux).  
  * *Accessibility Integration:* Customize UI configuration templates (weasel.custom.yaml and squirrel.custom.yaml) to output massive visual candidates, high-contrast highlighting, and scanning options tailored for single-button switches and eye-gaze control modules.

## **5\. Operational To-Do List & Milestones**

| Task ID | Work Package | Description | Target Resource | Status |
| :---- | :---- | :---- | :---- | :---- |
| **T-101** | WP1 | Download BCI-AV 2025 dataset (bliss\_svg\_id.zip, Excel) | BCI-AV 2025 URL | ⬜ Pending |
| **T-102** | WP1 | Extract SVGs and generate normalized JSON files with glosses | AI Agent (Data) | ⬜ Pending |
| **T-103** | WP1 | Parse Excel derivations to calculate lexical collation index | AI Agent (Data) | ⬜ Pending |
| **T-201** | WP2 | Build open-source base outlines using SVGs normalized to 1000 UPM | AI Agent (Font) | ⬜ Pending |
| **T-202** | WP2 | Calibrate anchor coordinates using Calibration Tool | **Specialist Consultant** | ⬜ Pending |
| **T-203** | WP2 | Programmatically compile GPOS & GSUB rules into .otf | AI Agent (Font) | ⬜ Pending |
| **T-301** | WP3 | Scaffold RIME YAML schema (blissymbols.schema.yaml) | AI Agent (App) | ⬜ Pending |
| **T-302** | WP3 | Compile lexical dictionaries (blissymbols.dict.yaml) for candidates | AI Agent (App) | ⬜ Pending |
| **T-303** | WP3 | Deploy and test Bliss-RIME on Weasel, Squirrel, and native switches | Humans (End-Users) | ⬜ Pending |

