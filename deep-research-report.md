# Project Implementation Prompt for the Code-Switching RAG System

## Executive Summary  
Implement an end-to-end, code-switching–aware Retrieval-Augmented Generation (RAG) chatbot exactly as described in Juvale et al. (2026). The system uses a two-part web UI: (1) a document-upload interface that ingests PDF/TXT/DOC files into a vector search index, and (2) a chat interface that answers user queries via a RAG pipeline. Use the SETU-RAG architecture’s methods: measure the query’s Code-Mixing Index (CMI) to route retrieval, expand queries into transliteration/translation views, and condition generation on the user’s language mix. Follow the paper’s specifications for models, data flow, and metrics; any unspecified choices (e.g. exact embedding model) should be flagged for user approval.  

## Task 1: Knowledge-Ingestion Pipeline (Document Upload Interface)  
- **Description:** Build a web page (or API endpoint) for users to upload documents (PDF, DOC/DOCX, TXT). Upon upload, parse text and split into passages for embedding. Store embeddings and metadata in a local vector database.  
- **Inputs:** Uploaded files (`.pdf`, `.docx`, `.txt`).  
- **Outputs:** Indexed document chunks with embeddings in a local store; metadata (original filename, language tag, chunk ID). A confirmation message or log.  
- **Folder Layout:**  
  ```
  project_root/
    data/
      raw_docs/        # store uploaded files
      chunks/          # store chunked text (optional)
      vector_db/       # persistence for vector store (e.g. Faiss index or Chroma DB files)
    app/
      ingest.py        # script/functions for parsing, chunking, embedding
      models.py        # load embedding and language models
      ... (other code)
  ```  
- **Implementation Steps:**  
  1. *File Handling:* On upload, save files under `data/raw_docs/`. Allow only safe extensions (e.g. `.pdf`, `.txt`, `.docx`) and set a size limit (e.g. 10–50MB). For security, validate file signatures and run antivirus/virus scanning on each file. Rename files to sanitized names (no user-controlled paths).  
  2. *Text Extraction:* Use libraries like `PyMuPDF` or `pdfplumber` for PDFs and `python-docx` for Word docs to extract text. For example:  
     ```python
     import fitz  # PyMuPDF
     doc = fitz.open(uploaded_pdf_path)
     text = ""
     for page in doc: text += page.get_text()
     ```  
  3. *Text Chunking:* Break extracted text into chunks (e.g. ~1000 characters with 200 overlap) to fit the embedding model’s context window. Use a sentence-splitter or sliding-window approach. Example with Python:  
     ```python
     from nltk import sent_tokenize
     sentences = sent_tokenize(text)
     chunks = []
     current = ""
     for sent in sentences:
         if len(current) + len(sent) > 1000:
             chunks.append(current); current = ""
         current += " " + sent
     if current: chunks.append(current)
     ```  
  4. *Embedding:* Load a multilingual embedding model (see **Alternatives Table** below). For each chunk, compute a vector. E.g.:  
     ```python
     from sentence_transformers import SentenceTransformer
     embed_model = SentenceTransformer('all-mpnet-base-v2')  # example model
     embeddings = embed_model.encode(chunks, show_progress_bar=True)
     ```  
  5. *Vector Database:* Store each chunk’s embedding in a vector index along with metadata `{doc_name, chunk_id, language}`. For example, using FAISS:  
     ```python
     import faiss
     index = faiss.IndexFlatL2(dim)  # dim = embedding dimension
     index.add(np.array(embeddings))
     ```  
     Or using Chroma DB:  
     ```python
     import chromadb
     client = chromadb.Client()
     collection = client.get_or_create_collection("docs")
     for i, chunk in enumerate(chunks):
         collection.add(documents=[chunk], embeddings=[embeddings[i]],
                        metadatas=[{"filename": filename, "chunk_id": i}])
     ```  
  6. *Update/Overwrite Behavior:* If a file with the same name is re-uploaded, overwrite or remove its previous chunks before re-indexing. Ensure idempotency by checking metadata in the DB and removing old entries.  
  7. *Command-Line Example:*  
     ```bash
     source .venv/bin/activate
     python app/ingest.py --input data/raw_docs/ --index data/vector_db/faiss_index
     ```  
- **Alternative Tools (Embeddings & Vector DB):**  

  | Component              | Options                                                | Pros                                              | Cons                                              | Recommendation      |
  |------------------------|--------------------------------------------------------|---------------------------------------------------|---------------------------------------------------|---------------------|
  | Embedding Models       | • **Sentence-BERT** (e.g. `all-mpnet-base-v2`)         | Good multilingual; easy via [🤗 Transformers].<br>Moderate size. | May not cover all Indic nuances. | **Use**: Sentence-BERT multilingual.<br>(Paper doesn’t specify exact model; user to confirm choice.) |
  |                        | • **LaBSE** (Language-Agnostic BERT)                   | Covers 109 languages (incl. Indic). Good cross-lingual similarity.    | Larger (768-dim), slower. | Alternative if better cross-lingual needed. |
  |                        | • **MuRIL** (Google’s Indic model)                     | Optimized for Indian languages.                    | May require special loading; size ~12–20GB for large. | Optional specialized choice. |
  | Vector Database / Index| • **FAISS** (Facebook)                                 | Very fast, supports CPU/GPU indices. Handles large data. | No built-in metadata; requires manual persistence. | **Use**: FAISS (GPU index on Colab T4) for speed. |
  |                        | • **ChromaDB**                                        | Pure Python, easy integration, supports metadata natively. | Slightly slower; less control over index tuning. | Alternative for simplicity; persists to disk. |
  |                        | • **Qdrant / Milvus** (standalone DBs)                 | Scalable, with REST/gRPC APIs.                     | Requires separate service; heavy for local. | Less ideal (no Docker). |
  
  *Choices should align with running on a single GPU with <16 GB as in Juvale et al. (2026). Confirm embedding model choice with user.*  

## Task 2: Chat-Based RAG Interface (Retrieval & Generation)  
- **Description:** Implement a chat page where the user enters a natural-language query. The system should retrieve relevant document chunks using a code-switching–aware strategy and then use an LLM to generate an answer grounded in those chunks.  
- **Inputs:** User query string (potentially code-switched Hindi-English text, e.g. “*mera refund kab tak aayega?*”).  
- **Outputs:** Generated answer string (mirroring user’s language mix and style, e.g. Hindi-English code-mix answer).  
- **Folder Layout:**  
  ```
  project_root/
    app/
      chat.py           # handles user queries and generates answers
      router.py         # functions for code-mix routing
      utils.py          # helpers (e.g., compute CMI, transliterate)
      templates/
        upload.html
        chat.html
      static/
        style.css       # white/blue theme CSS
  ```  
- **Implementation Steps:**  
  1. *Code-Mixing Detection:* Implement a function to compute the query’s **Code-Mixing Index (CMI)** and detect the matrix (primary) language. For example, count Indic script words vs. English words. You may use an Indic language identification model (e.g. `IndicLID` or a simple script) to tag words. Higher CMI indicates more mixing.  
  2. *Retrieval Router:* If CMI is below a threshold (monolingual query), do a single-language retrieval. If above, perform a **cross-lingual fan-out** as per SETU-RAG. For mixed queries, prepare multiple views (see next step).  
  3. *Multi-View Query Expansion:* Create up to four versions of the query : 
     - **Surface view:** the original query text.  
     - **Native-script view:** if the query is in Roman Hindi, transliterate to Devanagari (Indic script) using a transliteration library (e.g. Indic-Trans).  
     - **Matrix-canonical view:** if the matrix language is Hindi, convert English words to Hindi (e.g. with IndicTrans2) to produce a Hindi-centric query.  
     - **English-pivot view:** translate the query to English (using a model like IndicTrans2 or M2M100).  
     Embed each view separately and retrieve top-*k* chunks for each. Merge or re-rank the union of results.  
  4. *Retrieval:* Query the vector DB with each embedding. Return the top-*N* text chunks (with their source metadata) as context. Ensure at least one view yields relevant passages.  
  5. *Context Assembly:* Concatenate the retrieved chunks (e.g. most relevant 3–5) into a context string. You may prefix each chunk with its source ID.  
  6. *Generation Prompt:* Load a generative LLM (see **Alternatives Table** below). Construct a prompt that includes: the user’s original query, the user’s matrix language and CMI score, the retrieved context, and an instruction to answer in the same code-mixed style. For example:  
     ```
     # Context passages:
     {retrieved chunks...}
     
     # User Query:
     "mera refund kab tak aayega?"
     Matrix language: Hindi, CMI: 0.75 (high mixing).
     
     # Instruction:
     Answer the question in the same Hindi-English mixed style, using the context above for factual information.
     ```  
  7. *Answer Generation:* Run the LLM with the above prompt. Ensure the output respects the matrix language (Hindi or English) and mix ratio. For example, use “System” / “Assistant” instruction messages if using a chat model.  
  8. *Example Code Snippet:* Using Hugging Face Transformers for a local model:  
     ```python
     from transformers import AutoModelForCausalLM, AutoTokenizer
     tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-2-7b-chat-hf")
     model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-2-7b-chat-hf", 
                                                 load_in_4bit=True, device_map='auto')
     prompt = build_prompt(user_query, context, user_lang, user_cmi)
     inputs = tokenizer(prompt, return_tensors="pt")
     output = model.generate(**inputs, max_new_tokens=200)
     answer = tokenizer.decode(output[0], skip_special_tokens=True)
     ```  
  9. *Memory/GPU Management:* Because the models can be large, follow the paper’s strategy to keep total memory <16GB. You may load smaller/s quantized models (4-bit) and use batch inference carefully.  
  10. *Command-Line Example:*  
      ```bash
      python app/chat.py --query "mera refund kab tak aayega?"
      ```  

- **Alternative Tools (Generative LLMs):**

  | Model                 | Pros                                                       | Cons                                                      | Recommendation                 |
  |-----------------------|------------------------------------------------------------|-----------------------------------------------------------|--------------------------------|
  | **OpenAI GPT-3.5/4**  | State-of-art multilingual generation; strong code-switching ability. | Requires external API (no local inference); cost.      | Not suitable for local-only. |
  | **Meta LLaMA 2 (7B/13B)** | Open-weight; instruction-tuned; supports code-mixing to some extent.  | Large (requires GPU); 4-bit quant supported via BitsAndBytes. | **Use**: `meta-llama/Llama-2-7b-chat-hf` (4-bit). |
  | **Mistral 7B (Instruct)** | Open-source; high-quality on benchmarks; smaller than LLaMA-13B.    | Newly released; may need custom prompt tuning.           | Alternative if LLaMA not accessible. |
  | **Falcon 7B-Instruct** | Open-source, optimized; smaller memory footprint.             | Less tested on code-switch tasks.                        | Possible open-weight choice. |
  | **Others (GPT-NeoX, BLOOMZ)** | Multilingual support (BLOOM covers Indic); some support multilingual. | Very large models; may be too slow/rare.                   | Less practical locally. |

  *Recommended:* Use an open-weight, instruction-tuned model in 4-bit mode (e.g. Llama 2-7B) to fit GPU/16GB constraints. Confirm model choice with user.  

## Task 3: Frontend UI (Two Interfaces, White-and-Blue Theme)  
- **Description:** Create a simple web frontend with two pages/views: 
  1. **Upload Page:** A form to upload documents and trigger the ingestion pipeline.  
  2. **Chat Page:** A chat interface for user queries and displaying answers.  

- **Design Requirements:**  
  - **Theme:** Use a white background and blue accent colors (buttons, headers). No logo or project name displayed.  
  - **Accessibility:** Ensure high contrast text (blue on white), use ARIA labels on buttons/inputs, allow keyboard navigation, and include alt text for any icons.  
  - **Components:**  
    - *Upload Page:* File input field (accept `.pdf, .txt, .docx`), “Upload” button. Display a list of uploaded files and ingestion status. Example HTML snippet:  
      ```html
      <input type="file" id="fileInput" multiple accept=".pdf,.txt,.docx">
      <button id="uploadBtn">Upload Documents</button>
      <p id="status"></p>
      ```  
    - *Chat Page:* A conversation window showing user questions and bot answers, and an input box at bottom. Example:  
      ```html
      <div id="chatWindow"></div>
      <input type="text" id="userQuery" placeholder="Type your question...">
      <button id="sendBtn">Send</button>
      ```  
  - **Interactions:** On the Upload page, after the user selects files and clicks “Upload,” call the ingestion backend (e.g. via a POST request). Show success/failure message. On the Chat page, send each entered query to the RAG backend and append the returned answer to the chat window.  
  - **Color Styling:** In CSS (e.g. `static/style.css`):  
    ```css
    body { background-color: #ffffff; color: #000033; }
    button { background-color: #3366ff; color: white; border: none; padding: 8px; }
    input, textarea { border: 1px solid #3366ff; }
    ```  

- **File Layout for Frontend:**  
  ```
  project_root/
    templates/
      upload.html
      chat.html
    static/
      style.css
  ```  

- **Security Note:** Serve the site on HTTPS (for local dev use a self-signed cert if possible) and protect against CSRF on form submissions.

## Task 4: Local Environment Setup  
- **Description:** Prepare a Python virtual environment with all dependencies. Ensure it runs on CPU/GPU as needed.  
- **Steps:**  
  1. *Create and Activate venv:*  
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```  
  2. *Install Python Packages:* Specify exact versions compatible with paper’s setup. Example `requirements.txt`:  
     ```
     flask==2.2.5
     transformers==4.38.0
     sentence-transformers==2.2.2
     chromadb==0.3.21
     faiss-cpu==1.7.4  # or faiss-gpu
     torch==2.1.0       # or torch with CUDA if GPU available
     bitsandbytes==0.39.0
     nltk==3.8.1
     python-docx==0.8.11
     pymupdf==1.22.5
     indic-transliteration==1.0.5  # or similar for Indic translit
     sacremoses==0.0.53           # if needed for tokenization
     ```  
     Install via pip:  
     ```bash
     pip install -r requirements.txt
     ```  
  3. *GPU Notes:* If a GPU is present, install `torch` with CUDA support (e.g. `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118`). Ensure `accelerate` is configured if using 4-bit quantization.  
  4. *System Resources:* The paper ran on a single T4 GPU with 16 GB. Verify GPU memory usage does not exceed this (monitor during first test).  
  5. *Example Commands:*  
     ```bash
     source .venv/bin/activate
     pip install flask transformers sentence-transformers faiss-cpu chromadb bitsandbytes pymupdf python-docx
     ```  

## Task 5: Evaluation & Metrics  
- **Description:** Implement evaluation scripts to reproduce the paper’s metrics (RAGAS and code-switch metrics) on a test dataset.  
- **Metrics to Compute (as in paper):**  
  - *RAGAS Standard Axes:*  
    - **Faithfulness:** (e.g. percentage of facts in answer supported by context) – implement via overlap with ground-truth or evidence-checking.  
    - **Answer Relevance:** e.g. nDCG or precision/recall of retrieved passages vs. question relevance.  
    - **Context Precision/Recall:** Measure retrieval quality (ratio of relevant chunks returned).  
  - *Code-Switching–Native Metrics:*  
    - **CMI-Alignment:** Does the answer’s Code-Mixing Index match the user’s? (Compute CMI on answer vs. query).  
    - **Language-Consistency:** Is the matrix language of the answer the same as the user’s? (Simple language ID check).  
    - **Transliteration-Robustness:** Are transliterated terms correctly handled? (E.g. if query had Roman script, check if answer uses correct script forms).  
- **Implementation:**  
  - Prepare a small **evaluation dataset** of code-switched queries with reference answers and supporting documents (as used in the thesis). If unavailable, create a mock set of 50–100 Q&A pairs in Hindi-English.  
  - Write a Python evaluation script (`evaluate.py`) that:  
    1. Loads test queries and expected answers.  
    2. For each query, runs the RAG system to get an answer.  
    3. Calculates each metric: e.g. use BLEU/F1 for faithfulness against a reference answer, custom logic for CMI alignment (compare ratio of Hindi vs English tokens).  
    4. Logs results per query and computes averages. Output a CSV or JSON with columns like `query_id, faithfulness, relevance, prec, rec, CMI_align, lang_consistency, translit_robustness`.  
  - **Logging:** Print a summary table to console or save to `results/metrics.csv`. Include both standard and code-switch metrics.  
- **Output:** A final table of metric scores (averages) demonstrating that the system replicates the paper’s reported improvements on code-switched queries.  

## Task 6: Testing and Debugging  
- **Testing Steps:**  
  - **Unit Tests:** Write tests for key functions: file parsing, chunking, embedding indexing, CMI calculation, transliteration, and LLM prompting. For example, ensure `compute_CMI("mera refund kab") > 0`.  
  - **Integration Tests:**  
    - Upload a sample document via the interface and verify embeddings are stored.  
    - Issue a known query and check if retrieval returns expected passages (e.g. using a small test doc with unique keywords).  
    - Check the chat interface end-to-end: query → retrieval → generation.  
  - **Edge Cases:** Test non-code-switched queries (all English, all Hindi) to ensure system handles monolingual path correctly. Test extreme code-mixing (50/50) to ensure multi-view path.  
  - **Debugging Tips:** Log intermediate outputs (CMI score, chosen views, retrieved passages) to verify routing. If the answer output is off-target, examine LLM prompt and context.  
- **Example CLI Tests:**  
  ```bash
  # Test ingestion
  python app/ingest.py --input tests/sample1.txt --index data/vector_db/test_index
  
  # Test single query retrieval
  python app/chat.py --query "weather forecast Mumbai in Hindi"
  
  # Run evaluation
  python evaluate.py --testset tests/code_switch_dataset.json
  ```  
