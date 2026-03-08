# Azure AI Search — Index, Skillset, Indexer Setup

Use this document to recreate the Azure AI Search resources in a new Azure subscription.
All JSON bodies are ready to paste directly into the Azure Portal REST console or `curl`.

---

## Prerequisites

| Resource | Purpose |
|---|---|
| Azure AI Search service | Hosts the index, skillset, indexer |
| Azure Blob Storage container | Stores the source PDF manuals |
| Azure OpenAI service | `text-embedding-ada-002` deployment for chunk embeddings |

**Fill in these values** before running the API calls below:

```
SEARCH_ENDPOINT   = https://<your-search-resource>.search.windows.net
SEARCH_API_KEY    = <your-search-admin-key>
STORAGE_CONN_STR  = DefaultEndpointsProtocol=https;AccountName=<acct>;AccountKey=<key>;...
STORAGE_CONTAINER = <your-blob-container-name>
AOAI_ENDPOINT     = https://<your-openai-resource>.openai.azure.com/
AOAI_API_KEY      = <your-openai-key>
AOAI_EMBED_DEPLOY = text-embedding-ada-002
```

---

## Step 1 — Data Source

**REST endpoint:** `PUT {SEARCH_ENDPOINT}/datasources/pseg-techm-blob-ds?api-version=2024-05-01-preview`

```json
{
  "name": "pseg-techm-blob-ds",
  "type": "azureblob",
  "credentials": {
    "connectionString": "<STORAGE_CONN_STR>"
  },
  "container": {
    "name": "<STORAGE_CONTAINER>",
    "query": ""
  },
  "dataChangeDetectionPolicy": {
    "@odata.type": "#Microsoft.Azure.Search.HighWaterMarkChangeDetectionPolicy",
    "highWaterMarkColumnName": "metadata_storage_last_modified"
  }
}
```

---

## Step 2 — Index Schema

**REST endpoint:** `PUT {SEARCH_ENDPOINT}/indexes/rag-psegtechm-indexv01?api-version=2024-05-01-preview`

> **Important:** `chunk_id` is the document key. `contentVector` must match the
> dimensions of your embedding model: `1536` for `text-embedding-ada-002`.

```json
{
  "name": "rag-psegtechm-indexv01",
  "fields": [
    {
      "name": "chunk_id",
      "type": "Edm.String",
      "key": true,
      "searchable": false,
      "filterable": true,
      "retrievable": true,
      "sortable": false,
      "facetable": false
    },
    {
      "name": "content",
      "type": "Edm.String",
      "searchable": true,
      "filterable": false,
      "retrievable": true,
      "sortable": false,
      "facetable": false,
      "analyzer": "en.microsoft"
    },
    {
      "name": "contentVector",
      "type": "Collection(Edm.Single)",
      "searchable": true,
      "retrievable": false,
      "dimensions": 1536,
      "vectorSearchProfile": "pseg-hnsw-profile"
    },
    {
      "name": "source_file",
      "type": "Edm.String",
      "searchable": false,
      "filterable": true,
      "retrievable": true,
      "sortable": true,
      "facetable": true
    },
    {
      "name": "page_number",
      "type": "Edm.Int32",
      "searchable": false,
      "filterable": true,
      "retrievable": true,
      "sortable": true,
      "facetable": false
    },
    {
      "name": "source_url",
      "type": "Edm.String",
      "searchable": false,
      "filterable": false,
      "retrievable": true,
      "sortable": false,
      "facetable": false
    }
  ],
  "vectorSearch": {
    "profiles": [
      {
        "name": "pseg-hnsw-profile",
        "algorithm": "pseg-hnsw-algo"
      }
    ],
    "algorithms": [
      {
        "name": "pseg-hnsw-algo",
        "kind": "hnsw",
        "hnswParameters": {
          "m": 4,
          "efConstruction": 400,
          "efSearch": 500,
          "metric": "cosine"
        }
      }
    ]
  },
  "semantic": {
    "configurations": [
      {
        "name": "default",
        "prioritizedFields": {
          "contentFields": [
            { "fieldName": "content" }
          ],
          "keywordsFields": [
            { "fieldName": "source_file" }
          ]
        }
      }
    ]
  }
}
```

---

## Step 3 — Skillset

**REST endpoint:** `PUT {SEARCH_ENDPOINT}/skillsets/pseg-techm-skillset?api-version=2024-05-01-preview`

The pipeline:
1. **OCR** — extracts text from scanned/image PDFs (no-op for text PDFs)
2. **Merge** — combines native text with OCR text
3. **Split** — chunks merged text into 2 000-character pages with 200-char overlap
4. **Embedding** — calls Azure OpenAI to vectorise each chunk

```json
{
  "name": "pseg-techm-skillset",
  "description": "OCR + text split + Azure OpenAI embeddings for PSEG technical manuals",
  "skills": [
    {
      "@odata.type": "#Microsoft.Skills.Vision.OcrSkill",
      "name": "ocr",
      "description": "Extract text from image-based PDFs",
      "context": "/document/normalized_images/*",
      "defaultLanguageCode": "en",
      "detectOrientation": true,
      "inputs": [
        { "name": "image", "source": "/document/normalized_images/*" }
      ],
      "outputs": [
        { "name": "text",         "targetName": "text" },
        { "name": "layoutText",   "targetName": "layoutText" }
      ]
    },
    {
      "@odata.type": "#Microsoft.Skills.Text.MergeSkill",
      "name": "merge",
      "description": "Merge native PDF text with OCR text",
      "context": "/document",
      "insertPreTag": " ",
      "insertPostTag": " ",
      "inputs": [
        { "name": "text",         "source": "/document/content" },
        { "name": "itemsToInsert","source": "/document/normalized_images/*/text" },
        { "name": "offsets",      "source": "/document/normalized_images/*/contentOffset" }
      ],
      "outputs": [
        { "name": "mergedText",   "targetName": "merged_content" }
      ]
    },
    {
      "@odata.type": "#Microsoft.Skills.Text.SplitSkill",
      "name": "split",
      "description": "Split document into overlapping chunks for RAG",
      "context": "/document",
      "textSplitMode": "pages",
      "maximumPageLength": 2000,
      "pageOverlapLength": 200,
      "defaultLanguageCode": "en",
      "inputs": [
        { "name": "text", "source": "/document/merged_content" }
      ],
      "outputs": [
        { "name": "textItems", "targetName": "pages" }
      ]
    },
    {
      "@odata.type": "#Microsoft.Skills.Text.AzureOpenAIEmbeddingSkill",
      "name": "embedding",
      "description": "Generate Ada-002 embeddings for each chunk",
      "context": "/document/pages/*",
      "resourceUri": "<AOAI_ENDPOINT>",
      "apiKey": "<AOAI_API_KEY>",
      "deploymentId": "<AOAI_EMBED_DEPLOY>",
      "modelName": "text-embedding-ada-002",
      "dimensions": 1536,
      "inputs": [
        { "name": "text", "source": "/document/pages/*" }
      ],
      "outputs": [
        { "name": "embedding", "targetName": "contentVector" }
      ]
    }
  ],
  "indexProjections": {
    "selectors": [
      {
        "targetIndexName": "rag-psegtechm-indexv01",
        "parentKeyFieldName": "parent_id",
        "sourceContext": "/document/pages/*",
        "mappings": [
          { "name": "content",        "source": "/document/pages/*" },
          { "name": "contentVector",  "source": "/document/pages/*/contentVector" },
          { "name": "source_file",    "source": "/document/metadata_storage_name" },
          { "name": "source_url",     "source": "/document/metadata_storage_path" },
          { "name": "page_number",    "source": "/document/pages/*/pageNumber" }
        ]
      }
    ],
    "parameters": {
      "projectionMode": "generatedKeyAsId"
    }
  }
}
```

> **Note on `page_number`:** The `SplitSkill` exposes `/document/pages/*/pageNumber`
> (1-based integer). If this field is missing in your index after indexing, check that
> your Split skill output includes `pageNumber` — some API versions use `index` instead.
> Adjust the mapping if needed.

---

## Step 4 — Indexer

**REST endpoint:** `PUT {SEARCH_ENDPOINT}/indexers/pseg-techm-indexer?api-version=2024-05-01-preview`

```json
{
  "name": "pseg-techm-indexer",
  "dataSourceName": "pseg-techm-blob-ds",
  "targetIndexName": "rag-psegtechm-indexv01",
  "skillsetName": "pseg-techm-skillset",
  "schedule": { "interval": "PT2H" },
  "parameters": {
    "batchSize": 5,
    "maxFailedItems": 10,
    "maxFailedItemsPerBatch": 5,
    "configuration": {
      "dataToExtract": "contentAndMetadata",
      "imageAction": "generateNormalizedImages",
      "parsingMode": "default"
    }
  },
  "fieldMappings": [
    {
      "sourceFieldName": "metadata_storage_name",
      "targetFieldName": "source_file"
    },
    {
      "sourceFieldName": "metadata_storage_path",
      "targetFieldName": "source_url"
    }
  ],
  "outputFieldMappings": [
    {
      "sourceFieldName": "/document/pages/*/contentVector",
      "targetFieldName": "contentVector"
    }
  ]
}
```

---

## Step 5 — Run the Indexer

After creating all four resources, trigger an immediate run:

**REST endpoint:** `POST {SEARCH_ENDPOINT}/indexers/pseg-techm-indexer/run?api-version=2024-05-01-preview`

Check status:

**REST endpoint:** `GET {SEARCH_ENDPOINT}/indexers/pseg-techm-indexer/status?api-version=2024-05-01-preview`

---

## .env Values After Setup

Once indexing completes, set these in your `.env`:

```env
AZURE_SEARCH_ENDPOINT=https://<your-search-resource>.search.windows.net
AZURE_SEARCH_API_KEY=<your-search-admin-key>
AZURE_SEARCH_INDEX=rag-psegtechm-indexv01

SEARCH_CONTENT_FIELD=content
SEARCH_VECTOR_FIELD=contentVector
SEARCH_FILENAME_FIELD=source_file
SEARCH_PAGE_FIELD=page_number
SEARCH_CHUNK_ID_FIELD=chunk_id
SEARCH_URL_FIELD=source_url
SEARCH_SECTION_FIELD=
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `contentVector` is empty / all zeros | Embedding skill misconfigured | Check `AOAI_ENDPOINT` and `AOAI_API_KEY` in skillset |
| `page_number` is always null | SplitSkill `pageNumber` mapping wrong | Try mapping `source` to `/document/pages/*/index` instead |
| All queries return gate-rejected responses | Scores too low | Lower `MIN_AVG_SCORE` in `.env` — RRF hybrid scores range 0.01–0.033 |
| `chunk_id` key conflicts during reindex | Duplicate document IDs | Set `projectionMode: "generatedKeyAsId"` (already in skillset above) |
| Indexer fails on large PDFs | Timeout / batch too large | Reduce `batchSize` to 2, increase `maxFailedItems` |
