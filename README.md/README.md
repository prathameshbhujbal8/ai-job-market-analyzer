# 📊 AI Job Market Analyzer (12,894 Jobs)

An end-to-end data analytics project analyzing real job postings to identify skill demand and match resumes to job descriptions.
Built on 12,894 real job postings to analyze skill demand and optimize resumes using NLP, SQL, and BI tools.

---

## 🚀 Features

* TF-IDF resume–JD matching (NLP)
* SQL analysis using DuckDB
* Power BI dashboard with filters
* Excel skill demand analysis

---
Dataset not included due to size. Place `job_data.csv` inside /data folder before running.

## 📊 Key Insights

* SQL is the most in-demand skill (~37%)
* Excel and Python are core analyst tools
* Mid-level roles dominate the job market
* Remote jobs show strong demand for SQL

---

## 🛠 Tech Stack

Python, Pandas, Scikit-learn, Streamlit, SQL (DuckDB), Power BI, Excel

---

## ▶ Run Locally

```bash
pip install -r requirements.txt
streamlit run app/app.py
```
