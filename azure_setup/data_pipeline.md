# 🚀 Azure Data Pipeline (PostgreSQL → ADF → ADLS)

## 🎯 Objective

Build an automated pipeline to:

* Extract data from local PostgreSQL
* Store it in Azure Data Lake Storage (ADLS) as CSV
* Enable daily ingestion for ML training

---

## 🧱 Architecture

```
PostgreSQL (Local)
        ↓
Self-hosted Integration Runtime
        ↓
Azure Data Factory (Pipeline)
        ↓
Azure Data Lake Storage (CSV files)
```

---

## ⚙️ Steps Performed

### 1. Azure Setup

* Created **Azure Data Factory**
* Created **Storage Account (ADLS Gen2)**

---

### 2. Integration Runtime Setup

* Selected **Self-hosted Integration Runtime**
* Installed runtime on local machine
* Connected ADF to local PostgreSQL

---

### 3. Linked Services

#### PostgreSQL

* Connected using **Self-hosted IR**
* Provided host, port, credentials

#### ADLS

* Created linked service using:

  * **AutoResolveIntegrationRuntime**
  * Authentication via **Account Key**

---

### 4. Dataset Creation

#### Source Dataset (PostgreSQL)

* Selected table from PostgreSQL

#### Sink Dataset (ADLS - CSV)

* Format: **DelimitedText (CSV)**
* Path:

  * Container: `ml-data`
  * Folder: `training-data`

---

### 5. File Naming (Dynamic)

* Configured in dataset using expression:

```
@concat('data_', formatDateTime(utcNow(),'yyyy-MM-dd'), '.csv')
```

---

### 6. Pipeline Creation

* Created pipeline: `postgres_to_adls_pipeline`
* Added **Copy Data Activity**

#### Source Configuration

* Connected to PostgreSQL dataset
* Initially used full load:

```
SELECT * FROM your_table
```

#### Sink Configuration

* Connected to ADLS dataset
* Copy behavior: **Flatten hierarchy**
* File extension: `.csv`

---

### 7. Pipeline Execution

* Ran pipeline using **Debug**
* Pipeline executed successfully
* Output file created in ADLS

---

## 📂 Output Example

```
ml-data/training-data/data_2026-03-18.csv
```

---

## 🧠 Key Learnings

* ADF orchestrates data movement
* ADLS stores structured/unstructured data
* Integration Runtime connects on-prem to cloud
* Dataset defines file structure (path + name)
* Pipeline defines data flow

---

## 🚀 Next Step (Planned)

Implement **Incremental Loading**:

* Use `updated_at` column
* Load only new data
* Maintain watermark table

---

## 🎯 Interview Summary

"I built an Azure Data Factory pipeline to extract data from a local PostgreSQL database using a self-hosted integration runtime and stored it in Azure Data Lake Storage as CSV files with dynamic naming. The pipeline was tested and scheduled for automation."
