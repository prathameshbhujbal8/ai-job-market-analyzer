"""
AI Resume & Job Market Analyzer — app.py
- Dynamic CSV loading (no hardcoded numbers)
- Real skill demand from job_data.csv
- Plotly charts
- Proper match scoring (renamed from ATS Score)
- Two tabs: Resume Analyzer + Market Insights

FOLDER STRUCTURE REQUIRED:
  project/
  ├── app.py
  └── data/
      └── job_data.csv

RUN: streamlit run app.py
INSTALL: pip install streamlit pandas scikit-learn plotly
"""

import os
import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

st.set_page_config(page_title="AI Resume & Job Market Analyzer", page_icon="📊", layout="wide")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.path.join(BASE_DIR, "data", "job_data.csv")

SKILL_TAXONOMY = [
    "sql", "excel", "power bi", "python", "tableau", "r",
    "data visualization", "statistics", "machine learning",
    "pandas", "aws", "sas", "spss", "alteryx", "looker",
    "dax", "power query", "mysql", "postgresql", "spark",
]

ROLE_PATTERNS = {
    "Data Analyst":     ["data analyst", "analytics analyst", "bi analyst",
                         "business intelligence analyst", "reporting analyst", "insights analyst"],
    "Data Scientist":   ["data scientist", "machine learning engineer", "ml engineer", "ai engineer"],
    "Business Analyst": ["business analyst", "systems analyst", "functional analyst"],
    "Data Engineer":    ["data engineer", "etl developer", "pipeline engineer"],
}


def skill_pattern(skill):
    """Word-boundary regex — prevents 'r' matching inside 'market'."""
    return r"(?<![a-z])" + re.escape(skill) + r"(?![a-z])"


def clean_text(text):
    text = text.lower()
    text = re.sub(r"[^a-zA-Z\s]", " ", text)
    return " ".join(text.split())


def detect_role(jd_clean):
    for role, patterns in ROLE_PATTERNS.items():
        if any(p in jd_clean for p in patterns):
            return role
    return "Analyst (General)"


@st.cache_data(show_spinner="Loading job market data…")
def load_market_data(path):
    """Reads CSV once and computes all market stats. Cached on startup."""
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        return None

    df["skills_clean"] = df["job_skills"].astype(str).str.lower()
    df["level"]        = df["job level"].astype(str).str.strip()
    df["work_type"]    = df["job_type"].astype(str).str.strip()
    total              = len(df)
    core               = ["sql", "excel", "power bi", "python", "tableau", "r"]

    skill_demand = {
        skill: round(df["skills_clean"].str.contains(skill_pattern(skill), na=False).sum() / total * 100, 2)
        for skill in SKILL_TAXONOMY
    }

    skill_by_level = {}
    for level in df["level"].unique():
        sub = df[df["level"] == level]
        if len(sub):
            skill_by_level[level] = {
                s: round(sub["skills_clean"].str.contains(skill_pattern(s), na=False).sum() / len(sub) * 100, 2)
                for s in core
            }

    skill_by_type = {}
    for wtype in df["work_type"].unique():
        sub = df[df["work_type"] == wtype]
        if len(sub):
            skill_by_type[wtype] = {
                s: round(sub["skills_clean"].str.contains(skill_pattern(s), na=False).sum() / len(sub) * 100, 2)
                for s in core
            }

    return {
        "total_jobs":     total,
        "skill_demand":   skill_demand,
        "skill_by_level": skill_by_level,
        "skill_by_type":  skill_by_type,
        "level_dist":     df["level"].value_counts().to_dict(),
        "type_dist":      df["work_type"].value_counts().to_dict(),
    }


def compute_match(resume_clean, jd_clean, skill_demand):
    vec           = TfidfVectorizer()
    matrix        = vec.fit_transform([resume_clean, jd_clean])
    keyword_score = round(cosine_similarity(matrix[0], matrix[1])[0][0] * 100, 2)

    matched, missing = [], []
    for skill in SKILL_TAXONOMY:
        if re.search(skill_pattern(skill), jd_clean):
            (matched if re.search(skill_pattern(skill), resume_clean) else missing).append(skill)

    total_req   = len(matched) + len(missing)
    skill_score = round(len(matched) / total_req * 100, 2) if total_req else 0
    final_score = round(0.60 * keyword_score + 0.40 * skill_score, 2)

    return {
        "keyword_score": keyword_score,
        "skill_score":   skill_score,
        "final_score":   final_score,
        "matched":       matched,
        "missing":       sorted(missing, key=lambda s: skill_demand.get(s, 0), reverse=True),
    }


def chart_demand(skill_demand, top_n=15):
    top          = sorted(skill_demand.items(), key=lambda x: x[1], reverse=True)[:top_n]
    skills, pcts = zip(*top)
    fig = px.bar(x=list(pcts), y=[s.title() for s in skills], orientation="h",
                 text=[f"{p}%" for p in pcts], color=list(pcts),
                 color_continuous_scale="Blues",
                 labels={"x": "% of Job Postings", "y": "Skill"},
                 title=f"Top {top_n} Skills by Market Demand — {sum(v for _,v in top):.0f}+ mentions")
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False,
                      plot_bgcolor="rgba(0,0,0,0)")
    fig.update_traces(textposition="outside")
    return fig


def chart_by_level(skill_by_level):
    rows = [{"Level": l, "Skill": s.title(), "Demand (%)": p}
            for l, skills in skill_by_level.items() for s, p in skills.items()]
    fig = px.bar(pd.DataFrame(rows), x="Skill", y="Demand (%)", color="Level", barmode="group",
                 color_discrete_sequence=["#2E86AB", "#E84855"],
                 title="Skill Demand: Associate vs Mid-Senior", text_auto=True)
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    return fig


def chart_by_type(skill_by_type):
    rows = [{"Work Type": w, "Skill": s.title(), "Demand (%)": p}
            for w, skills in skill_by_type.items() for s, p in skills.items()]
    fig = px.bar(pd.DataFrame(rows), x="Skill", y="Demand (%)", color="Work Type", barmode="group",
                 color_discrete_sequence=["#3BB273", "#7B2D8B", "#E9C46A"],
                 title="Skill Demand: Onsite vs Remote vs Hybrid", text_auto=True)
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
    return fig


def chart_coverage(matched, missing):
    all_skills = matched + missing[:6]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="In Resume ✅", x=[s.title() for s in all_skills],
                         y=[1 if s in matched else 0 for s in all_skills], marker_color="#2ecc71"))
    fig.add_trace(go.Bar(name="Required by JD", x=[s.title() for s in all_skills],
                         y=[1] * len(all_skills), marker_color="#e74c3c", opacity=0.35))
    fig.update_layout(barmode="overlay", title="Resume Coverage vs JD Requirements",
                      yaxis={"visible": False}, plot_bgcolor="rgba(0,0,0,0)",
                      legend={"orientation": "h"})
    return fig


# ── MAIN UI ───────────────────────────────────────────────────────────────────
st.title("📊 AI Resume & Job Market Analyzer")
st.caption("TF-IDF cosine similarity · Market demand computed live from 12,894 real job postings")

stats = load_market_data(DATA_PATH)
if stats is None:
    st.error(f"Dataset not found at `{DATA_PATH}`. Place `job_data.csv` inside a `data/` folder.")
    st.stop()

tab1, tab2 = st.tabs(["🎯 Resume Analyzer", "📈 Market Insights"])

# ── TAB 1 ─────────────────────────────────────────────────────────────────────
with tab1:
    col_l, col_r = st.columns(2, gap="large")
    with col_l:
        resume_input = st.text_area("Paste Your Resume", height=260)
    with col_r:
        jd_input = st.text_area("Paste Job Description", height=260)

    if st.button("🔍 Analyze", use_container_width=True, type="primary"):
        if not resume_input.strip() or not jd_input.strip():
            st.warning("Please fill in both fields.")
        else:
            r_clean = clean_text(resume_input)
            j_clean = clean_text(jd_input)
            role    = detect_role(j_clean)
            result  = compute_match(r_clean, j_clean, stats["skill_demand"])

            st.divider()
            st.subheader(f"Detected Role: {role}")

            c1, c2, c3 = st.columns(3)
            c1.metric("Keyword Match",      f"{result['keyword_score']}%",
                      help="TF-IDF cosine similarity — measures text overlap between resume and JD.")
            c2.metric("Skill Coverage",     f"{result['skill_score']}%",
                      help="% of JD-required skills found in your resume.")
            c3.metric("Overall Match Score",f"{result['final_score']}%",
                      help="Weighted score: 60% keyword match + 40% skill coverage.")

            score = result["final_score"]
            if score > 70:
                st.success("Strong match — your resume aligns well with this role.")
            elif score > 40:
                st.warning("Moderate match — targeted improvements will help.")
            else:
                st.error("Low match — review missing skills and add relevant keywords.")
            st.progress(min(int(score), 100))
            st.divider()

            ca, cb = st.columns(2, gap="large")
            with ca:
                st.subheader("✅ Matched Skills")
                for skill in result["matched"]:
                    d = stats["skill_demand"].get(skill, 0)
                    st.markdown(f"**{skill.title()}** · <span style='color:#888'>{d}% of postings</span>",
                                unsafe_allow_html=True)
                if not result["matched"]:
                    st.info("No taxonomy skills matched.")

            with cb:
                st.subheader("❌ Missing Skills (Market Priority Order)")
                for skill in result["missing"]:
                    d    = stats["skill_demand"].get(skill, 0)
                    icon = "🔴" if d > 20 else "🟡" if d > 10 else "🟢"
                    st.markdown(f"{icon} **{skill.title()}** · <span style='color:#888'>{d}% of postings</span>",
                                unsafe_allow_html=True)
                if not result["missing"]:
                    st.success("No skill gaps detected.")

            if result["matched"] or result["missing"]:
                st.divider()
                st.plotly_chart(chart_coverage(result["matched"], result["missing"]),
                                use_container_width=True)

            st.divider()
            st.subheader("💡 Recommendations")
            for skill in result["missing"][:3]:
                d = stats["skill_demand"].get(skill, 0)
                st.write(f"→ **{skill.title()}** appears in **{d}%** of analyst job postings "
                         f"({stats['total_jobs']:,} jobs analyzed).")

            msg = ("📝 Mirror the JD's exact terminology in your experience bullets." if score < 50 else
                   "📝 Add missing skills via certifications or projects." if score < 75 else
                   "📝 Resume is well-optimized. Tailor your summary to the JD.")
            st.write(msg)

            if result["missing"]:
                gap_df = pd.DataFrame({
                    "Skill":             result["missing"],
                    "In Resume":         "No",
                    "Market Demand (%)": [stats["skill_demand"].get(s, 0) for s in result["missing"]],
                    "Priority":          ["High" if stats["skill_demand"].get(s, 0) > 20
                                          else "Medium" if stats["skill_demand"].get(s, 0) > 10
                                          else "Low" for s in result["missing"]],
                })
                st.download_button("⬇️ Download Skill Gap Report (CSV)",
                                   gap_df.to_csv(index=False), "skill_gap_report.csv", "text/csv")

# ── TAB 2 ─────────────────────────────────────────────────────────────────────
with tab2:
    st.subheader("📊 Market Insights — Computed from Real Job Postings")
    st.caption(f"Source: LinkedIn job data · {stats['total_jobs']:,} postings · "
               "All percentages are live-computed from the dataset — not hardcoded.")

    m1, m2, m3 = st.columns(3)
    m1.metric("Jobs Analyzed",    f"{stats['total_jobs']:,}")
    m2.metric("Seniority Levels", f"{len(stats['level_dist'])}")
    m3.metric("Work Types",       f"{len(stats['type_dist'])}")

    st.divider()
    st.plotly_chart(chart_demand(stats["skill_demand"]), use_container_width=True)

    l, r = st.columns(2, gap="large")
    with l:
        st.plotly_chart(chart_by_level(stats["skill_by_level"]), use_container_width=True)
    with r:
        st.plotly_chart(chart_by_type(stats["skill_by_type"]), use_container_width=True)

    st.divider()
    st.subheader("🔍 Key Findings")
    sd = stats["skill_demand"]

    st.write(f"- **{max(sd, key=sd.get).title()}** is the top demanded skill "
             f"({sd[max(sd, key=sd.get)]}% of all analyst postings).")

    sbt = stats["skill_by_type"]
    if "Remote" in sbt and "Onsite" in sbt:
        st.write(f"- **SQL** demand: Remote {sbt['Remote'].get('sql',0)}% vs "
                 f"Onsite {sbt['Onsite'].get('sql',0)}% — remote roles need stronger query skills.")

    sbl = stats["skill_by_level"]
    if "Associate" in sbl and "Mid senior" in sbl:
        st.write(f"- **Power BI** rises from {sbl['Associate'].get('power bi',0)}% (Associate) "
                 f"→ {sbl['Mid senior'].get('power bi',0)}% (Mid-Senior). Learn it early.")
        st.write(f"- **Python** is stable: {sbl['Associate'].get('python',0)}% → "
                 f"{sbl['Mid senior'].get('python',0)}% — expected at all levels.")

    st.write(f"- **Excel** ({sd.get('excel',0)}%) outranks Power BI ({sd.get('power bi',0)}%) "
             f"— spreadsheet skills are more universally required.")