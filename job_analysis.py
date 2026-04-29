"""
job_analysis.py — Job Market Skill Demand Analysis
====================================================
Analyzes job_data.csv (12,894 analyst job postings) to produce:

  1.  Dataset summary
  2.  Overall skill demand (%)
  3.  Skill demand by seniority level
  4.  Skill demand by work type (Onsite / Remote / Hybrid)
  5.  Skill demand by country
  6.  SQL co-occurrence analysis
  7.  Job level × Work type cross-tab
  8.  Skill stack segmentation
  9.  Business insights (auto-generated from real data)
  10. Charts (bar, grouped bar, saved as PNG if --export used)

USAGE:
    python job_analysis.py
    python job_analysis.py --path data/job_data.csv
    python job_analysis.py --path data/job_data.csv --top 15 --export

INSTALL:
    pip install pandas matplotlib
"""

import argparse
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# ── CONFIGURATION ─────────────────────────────────────────────────────────────

DEFAULT_CSV = "data/job_data.csv"

# Full skill taxonomy used for demand analysis
# Word-boundary regex applied to each — prevents 'r' matching inside 'market'
SKILLS = [
    "sql", "excel", "power bi", "python", "tableau", "r",
    "data visualization", "statistics", "machine learning",
    "pandas", "aws", "sas", "spss", "alteryx", "looker",
    "dax", "power query", "mysql", "postgresql", "spark",
]

# Core 6 skills used in cross-tabulation charts
CORE_SKILLS = ["sql", "excel", "power bi", "python", "tableau", "r"]

# Required columns — script exits if any are missing
REQUIRED_COLUMNS = {"job_skills", "job level", "job_type", "job_title", "company"}


# ── HELPERS ───────────────────────────────────────────────────────────────────

def skill_pattern(skill: str) -> str:
    """
    Word-boundary regex for skill matching.
    Prevents false positives: 'r' won't match inside 'market', 'career', etc.
    Uses negative lookbehind/lookahead instead of \b (more reliable for short skills).
    """
    return r"(?<![a-z])" + re.escape(skill) + r"(?![a-z])"


def section(title: str) -> None:
    """Print a clearly visible section header."""
    width = 60
    print(f"\n{'─' * width}")
    print(f"  {title}")
    print(f"{'─' * width}")


def bar_in_terminal(pct: float, max_width: int = 30) -> str:
    """Return a simple ASCII bar proportional to the percentage."""
    filled = int((pct / 100) * max_width)
    return "█" * filled + "░" * (max_width - filled)


# ── LOAD DATA ─────────────────────────────────────────────────────────────────

def load_data(path: str) -> pd.DataFrame:
    from pathlib import Path
    import sys
    import pandas as pd

    p = Path(path)

    if not p.exists():
        print(f"\n[ERROR] File not found: {path}")
        sys.exit(1)

    df = pd.read_csv(p)
    print(f"[INFO] Loaded {len(df):,} rows from '{path}'")

    # 🔥 NEW: Flexible column detection
    col_map = {c.lower().replace(" ", "_"): c for c in df.columns}

    required_keys = ["job_skills", "job_level", "job_type", "job_title", "company"]

    missing = [k for k in required_keys if k not in col_map]
    if missing:
        print(f"[ERROR] Missing required columns: {missing}")
        print(f"Available columns: {list(df.columns)}")
        sys.exit(1)

    # 🔥 Use mapped columns (robust)
    df["skills_clean"] = df[col_map["job_skills"]].astype(str).str.lower()
    df["level"]        = df[col_map["job_level"]].astype(str).str.strip()
    df["work_type"]    = df[col_map["job_type"]].astype(str).str.strip()
    df["title_clean"]  = df[col_map["job_title"]].astype(str).str.lower()

    # Null info
    null_skills = df[col_map["job_skills"]].isnull().sum()
    if null_skills > 0:
        print(f"[INFO] {null_skills:,} rows missing job_skills")

    return df


# ── ANALYSIS FUNCTIONS ────────────────────────────────────────────────────────

def dataset_summary(df: pd.DataFrame) -> None:
    """Print high-level dataset overview."""
    section("1. DATASET SUMMARY")

    total      = len(df)
    with_skills = df["job_skills"].notna().sum()

    print(f"  Total job postings   : {total:,}")
    print(f"  Postings with skills : {with_skills:,} ({with_skills/total*100:.1f}%)")
    print(f"  Postings missing     : {total - with_skills:,}")
    print(f"  Unique companies     : {df['company'].nunique():,}")

    print(f"\n  Seniority levels:")
    for level, count in df["level"].value_counts().items():
        print(f"    {level:<15}  {count:>6,}  ({count/total*100:.1f}%)  "
              f"{bar_in_terminal(count/total*100, 20)}")

    print(f"\n  Work types:")
    for wtype, count in df["work_type"].value_counts().items():
        print(f"    {wtype:<15}  {count:>6,}  ({count/total*100:.1f}%)  "
              f"{bar_in_terminal(count/total*100, 20)}")

    if "search_country" in df.columns:
        print(f"\n  Countries:")
        for country, count in df["search_country"].value_counts().items():
            print(f"    {country:<20}  {count:>6,}  ({count/total*100:.1f}%)")


def overall_skill_demand(df: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
    """
    Compute % of all job postings that mention each skill.
    Uses word-boundary regex to prevent false matches.
    Returns sorted DataFrame.
    """
    section("2. OVERALL SKILL DEMAND")

    total = len(df)
    rows  = []

    for skill in SKILLS:
        count = df["skills_clean"].str.contains(skill_pattern(skill), na=False).sum()
        rows.append({
            "skill":   skill,
            "count":   count,
            "pct":     round(count / total * 100, 2),
        })

    result = (
        pd.DataFrame(rows)
        .sort_values("pct", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    result.index += 1  # 1-based rank

    # Print with ASCII bars
    print(f"\n  {'Rank':<5} {'Skill':<22} {'Count':>6}  {'Demand':>7}  Visual")
    print("  " + "-" * 58)
    for rank, row in result.iterrows():
        bar = bar_in_terminal(row["pct"], 25)
        print(f"  {rank:<5} {row['skill'].title():<22} "
              f"{int(row['count']):>6,}  {row['pct']:>6.2f}%  {bar}")

    return result


def skill_demand_by_level(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute skill demand % broken down by seniority level.
    Answers: 'Of Associate jobs, what % require SQL?'
    (NOT: 'Of SQL jobs, what share are Associate?' — that's a different question)
    """
    section("3. SKILL DEMAND BY SENIORITY LEVEL")

    rows = []
    for level in sorted(df["level"].unique()):
        sub = df[df["level"] == level]
        n   = len(sub)
        for skill in CORE_SKILLS:
            cnt = sub["skills_clean"].str.contains(skill_pattern(skill), na=False).sum()
            rows.append({
                "level": level,
                "skill": skill,
                "pct":   round(cnt / n * 100, 2),
                "n_jobs": n,
            })

    result = pd.DataFrame(rows)

    # Pivot for readability
    pivot = result.pivot(index="skill", columns="level", values="pct")
    pivot.index = [s.title() for s in pivot.index]
    print()
    print(pivot.to_string())

    # Auto-generate insight from data
    if "Mid senior" in pivot.columns and "Associate" in pivot.columns:
        delta   = (pivot["Mid senior"] - pivot["Associate"]).sort_values(ascending=False)
        up_sk   = delta.index[0]
        up_diff = delta.iloc[0]
        dn_sk   = delta.index[-1]
        dn_diff = abs(delta.iloc[-1])
        direction = "higher" if up_diff > 0 else "lower"
        print(f"\n  → Insight: {up_sk} demand is {abs(up_diff):.1f}pp {direction} at "
              f"Mid-Senior than Associate — invest in it early for career progression.")
        print(f"  → Insight: {dn_sk} demand drops {dn_diff:.1f}pp at Mid-Senior — "
              f"it's treated as a baseline skill, expected by default.")

    return result


def skill_demand_by_work_type(df: pd.DataFrame) -> pd.DataFrame:
    """Compute skill demand % split by Onsite / Remote / Hybrid."""
    section("4. SKILL DEMAND BY WORK TYPE (Onsite / Remote / Hybrid)")

    rows = []
    for wtype in df["work_type"].unique():
        sub = df[df["work_type"] == wtype]
        n   = len(sub)
        for skill in CORE_SKILLS:
            cnt = sub["skills_clean"].str.contains(skill_pattern(skill), na=False).sum()
            rows.append({
                "work_type": wtype,
                "skill":     skill,
                "pct":       round(cnt / n * 100, 2),
                "n_jobs":    n,
            })

    result = pd.DataFrame(rows)
    pivot  = result.pivot(index="skill", columns="work_type", values="pct")
    pivot.index = [s.title() for s in pivot.index]
    print()
    print(pivot.to_string())

    # Auto-generate insight
    if "Remote" in pivot.columns and "Onsite" in pivot.columns:
        if "sql" in [s.lower() for s in pivot.index]:
            sql_row = pivot.loc[[s for s in pivot.index if s.lower() == "sql"][0]]
            rm_sql  = sql_row.get("Remote", 0)
            os_sql  = sql_row.get("Onsite", 0)
            diff    = round(rm_sql - os_sql, 2)
            higher  = "Remote" if diff > 0 else "Onsite"
            print(f"\n  → Insight: SQL demand is {abs(diff):.1f}pp higher in {higher} roles "
                  f"({rm_sql}% Remote vs {os_sql}% Onsite).")
            if higher == "Remote":
                print(f"             Remote employers rely more on independent query skills — "
                      f"prioritise SQL if targeting remote positions.")

    return result


def skill_demand_by_country(df: pd.DataFrame) -> pd.DataFrame:
    """Compute skill demand % split by search country."""
    if "search_country" not in df.columns:
        return pd.DataFrame()

    section("5. SKILL DEMAND BY COUNTRY")

    rows = []
    for country in df["search_country"].value_counts().index:
        sub = df[df["search_country"] == country]
        n   = len(sub)
        for skill in ["sql", "excel", "python", "power bi"]:
            cnt = sub["skills_clean"].str.contains(skill_pattern(skill), na=False).sum()
            rows.append({
                "country": country,
                "skill":   skill.title(),
                "pct":     round(cnt / n * 100, 2),
                "n_jobs":  n,
            })

    result = pd.DataFrame(rows)
    pivot  = result.pivot(index="country", columns="skill", values="pct")
    print()
    print(pivot.to_string())
    return result


def sql_cooccurrence(df: pd.DataFrame) -> pd.DataFrame:
    """
    Which skills most frequently appear alongside SQL?
    Uses anchor-filter approach: filter to SQL jobs, then count each other skill.
    """
    section("6. SKILL CO-OCCURRENCE WITH SQL")

    sql_jobs = df[df["skills_clean"].str.contains(skill_pattern("sql"), na=False)]
    n_sql    = len(sql_jobs)

    if n_sql == 0:
        print("  No SQL jobs found.")
        return pd.DataFrame()

    print(f"  Total SQL jobs in dataset: {n_sql:,} "
          f"({n_sql/len(df)*100:.1f}% of all postings)\n")

    rows = []
    for skill in SKILLS:
        if skill == "sql":
            continue
        cnt = sql_jobs["skills_clean"].str.contains(skill_pattern(skill), na=False).sum()
        rows.append({
            "skill":          skill,
            "count":          cnt,
            "co_pct":         round(cnt / n_sql * 100, 2),
        })

    result = (
        pd.DataFrame(rows)
        .sort_values("co_pct", ascending=False)
        .head(8)
        .reset_index(drop=True)
    )

    print(f"  {'Skill':<22} {'Co-occurrence':>14}  Visual")
    print("  " + "-" * 52)
    for _, row in result.iterrows():
        bar = bar_in_terminal(row["co_pct"], 25)
        print(f"  {row['skill'].title():<22} {row['co_pct']:>12.1f}%  {bar}")

    top3 = result["skill"].head(3).str.title().tolist()
    print(f"\n  → Insight: The core DA stack is SQL + {' + '.join(top3)}.")
    print(f"             Mastering these 4 skills covers the majority of analyst postings.")

    return result


def level_worktype_crosstab(df: pd.DataFrame) -> pd.DataFrame:
    """
    Two-dimensional cross-tab: seniority × work type.
    Equivalent to an Excel pivot table with two row dimensions.
    """
    section("7. JOB LEVEL × WORK TYPE CROSS-TAB")

    ct = pd.crosstab(
        df["level"],
        df["work_type"],
        margins=True,
        margins_name="Total",
    )
    print()
    print(ct.to_string())

    # Show % within level
    print("\n  % within each seniority level:")
    pct_table = pd.crosstab(
        df["level"],
        df["work_type"],
        normalize="index",
    ).round(4) * 100
    print(pct_table.to_string(float_format="{:.1f}%".format))

    return ct


def skill_stack_segmentation(df: pd.DataFrame) -> pd.DataFrame:
    """
    Classify each job posting by which skill combination it requires.
    Shows what % of the market expects each stack.
    """
    section("8. SKILL STACK SEGMENTATION (CASE WHEN Logic)")

    sl = df["skills_clean"]

    df_seg = df.copy()
    df_seg["stack"] = "Other / No core skill"

    mask_sql    = sl.str.contains(skill_pattern("sql"),      na=False)
    mask_python = sl.str.contains(skill_pattern("python"),   na=False)
    mask_pbi    = sl.str.contains("power bi",                na=False)
    mask_tab    = sl.str.contains(skill_pattern("tableau"),  na=False)
    mask_excel  = sl.str.contains(skill_pattern("excel"),    na=False)

    # Order matters — most specific first
    df_seg.loc[mask_sql & mask_python,          "stack"] = "SQL + Python"
    df_seg.loc[mask_sql & mask_pbi,             "stack"] = "SQL + Power BI"
    df_seg.loc[mask_sql & mask_tab,             "stack"] = "SQL + Tableau"
    df_seg.loc[mask_sql & mask_excel & ~mask_python & ~mask_pbi & ~mask_tab,
                                                "stack"] = "SQL + Excel only"
    df_seg.loc[mask_sql & ~mask_python & ~mask_pbi & ~mask_tab & ~mask_excel,
                                                "stack"] = "SQL only"
    df_seg.loc[~mask_sql & mask_excel,          "stack"] = "Excel only"

    total  = len(df_seg)
    result = (
        df_seg["stack"]
        .value_counts()
        .reset_index()
    )
    result.columns   = ["stack_type", "job_count"]
    result["pct"]    = (result["job_count"] / total * 100).round(2)

    print(f"\n  {'Stack Type':<25} {'Jobs':>7}  {'%':>7}  Visual")
    print("  " + "-" * 60)
    for _, row in result.iterrows():
        bar = bar_in_terminal(row["pct"], 20)
        print(f"  {row['stack_type']:<25} {int(row['job_count']):>7,}  "
              f"{row['pct']:>6.1f}%  {bar}")

    return result


def business_insights(df: pd.DataFrame) -> None:
    """
    Auto-generate business insights from computed statistics.
    All numbers come directly from the dataset — nothing hardcoded.
    """
    section("9. KEY BUSINESS INSIGHTS (Auto-generated from Dataset)")

    total = len(df)
    sl    = df["skills_clean"]

    # Compute all numbers live
    skill_counts = {
        s: sl.str.contains(skill_pattern(s), na=False).sum()
        for s in SKILLS
    }
    skill_pcts = {s: round(c / total * 100, 2) for s, c in skill_counts.items()}

    # Top skill
    top_skill = max(skill_pcts, key=skill_pcts.get)
    print(f"\n  1. {top_skill.upper()} ({skill_pcts[top_skill]}%) is the most demanded skill.")
    print(f"     Without it, candidates are excluded from {skill_pcts[top_skill]:.0f}% of postings.")

    # Excel vs Power BI
    ex_pct = skill_pcts.get("excel", 0)
    pbi_pct = skill_pcts.get("power bi", 0)
    print(f"\n  2. Excel ({ex_pct}%) outranks Power BI ({pbi_pct}%) in raw demand.")
    print(f"     Master Excel before BI tools — it's a more universal baseline.")

    # Remote vs Onsite SQL
    remote = df[df["work_type"] == "Remote"]
    onsite = df[df["work_type"] == "Onsite"]
    if len(remote) and len(onsite):
        rm_sql = round(remote["skills_clean"].str.contains(skill_pattern("sql"), na=False).sum()
                       / len(remote) * 100, 2)
        os_sql = round(onsite["skills_clean"].str.contains(skill_pattern("sql"), na=False).sum()
                       / len(onsite) * 100, 2)
        diff   = round(rm_sql - os_sql, 2)
        higher = "Remote" if diff > 0 else "Onsite"
        print(f"\n  3. SQL demand is {abs(diff):.1f}pp higher in {higher} roles "
              f"({rm_sql}% Remote vs {os_sql}% Onsite).")
        print(f"     Prioritise SQL if targeting remote positions.")

    # Power BI: level progression
    assoc    = df[df["level"] == "Associate"]
    midsenior = df[df["level"] == "Mid senior"]
    if len(assoc) and len(midsenior):
        as_pbi = round(assoc["skills_clean"].str.contains("power bi", na=False).sum()
                       / len(assoc) * 100, 2)
        ms_pbi = round(midsenior["skills_clean"].str.contains("power bi", na=False).sum()
                       / len(midsenior) * 100, 2)
        diff   = round(ms_pbi - as_pbi, 2)
        print(f"\n  4. Power BI demand rises from {as_pbi}% (Associate) to {ms_pbi}% (Mid-Senior).")
        print(f"     A +{diff}pp jump — learning it early accelerates career progression.")

    # Core stack coverage
    sql_jobs = sl.str.contains(skill_pattern("sql"), na=False)
    py_jobs  = sl.str.contains(skill_pattern("python"), na=False)
    pbi_jobs = sl.str.contains("power bi", na=False)
    tab_jobs = sl.str.contains(skill_pattern("tableau"), na=False)
    core_any = (sql_jobs | py_jobs | pbi_jobs | tab_jobs).sum()
    print(f"\n  5. SQL + Python + Power BI + Tableau covers {core_any/total*100:.1f}% of analyst postings.")
    print(f"     A candidate proficient in all 4 has coverage across {core_any:,} of {total:,} jobs.")


# ── CHARTS ────────────────────────────────────────────────────────────────────

def chart_overall_demand(df_demand: pd.DataFrame, export: bool = False) -> None:
    """Horizontal bar chart — top N skills by market demand."""
    fig, ax = plt.subplots(figsize=(11, 6))

    colors = plt.cm.Blues_r(
        [i / len(df_demand) * 0.7 + 0.15 for i in range(len(df_demand))]
    )
    bars = ax.barh(
        df_demand["skill"].str.title(),
        df_demand["pct"],
        color=colors,
        edgecolor="white",
        linewidth=0.5,
    )
    ax.bar_label(bars, fmt="%.1f%%", padding=4, fontsize=9)
    ax.set_xlabel("% of Job Postings", fontsize=11)
    ax.set_title("Analyst Skill Demand — Based on 12,894 Real Job Postings",
                 fontsize=13, fontweight="bold", pad=15)
    ax.set_xlim(0, df_demand["pct"].max() * 1.25)
    ax.invert_yaxis()
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_facecolor("#fafafa")
    fig.tight_layout()

    if export:
        Path("output").mkdir(exist_ok=True)
        fig.savefig("output/skill_demand.png", dpi=150, bbox_inches="tight")
        print("[SAVED] output/skill_demand.png")
    plt.show()


def chart_by_level(df_level: pd.DataFrame, export: bool = False) -> None:
    """Grouped bar chart — skill demand split by seniority level."""
    pivot = df_level.pivot(index="skill", columns="level", values="pct")

    fig, ax = plt.subplots(figsize=(11, 5))
    pivot.plot(kind="bar", ax=ax, color=["#2E86AB", "#E84855"],
               edgecolor="white", linewidth=0.5)
    ax.set_xticklabels([s.title() for s in pivot.index], rotation=30, ha="right")
    ax.set_ylabel("% of Job Postings", fontsize=11)
    ax.set_xlabel("")
    ax.set_title("Skill Demand: Associate vs Mid-Senior", fontsize=13, fontweight="bold")
    ax.legend(title="Seniority Level")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_facecolor("#fafafa")
    fig.tight_layout()

    if export:
        Path("output").mkdir(exist_ok=True)
        fig.savefig("output/skill_by_level.png", dpi=150, bbox_inches="tight")
        print("[SAVED] output/skill_by_level.png")
    plt.show()


def chart_by_type(df_type: pd.DataFrame, export: bool = False) -> None:
    """Grouped bar chart — skill demand split by work arrangement."""
    pivot = df_type.pivot(index="skill", columns="work_type", values="pct")

    type_colors = {"Onsite": "#3BB273", "Remote": "#7B2D8B", "Hybrid": "#E9C46A"}
    colors = [type_colors.get(c, "#999") for c in pivot.columns]

    fig, ax = plt.subplots(figsize=(11, 5))
    pivot.plot(kind="bar", ax=ax, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_xticklabels([s.title() for s in pivot.index], rotation=30, ha="right")
    ax.set_ylabel("% of Job Postings", fontsize=11)
    ax.set_xlabel("")
    ax.set_title("Skill Demand: Onsite vs Remote vs Hybrid", fontsize=13, fontweight="bold")
    ax.legend(title="Work Type")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_facecolor("#fafafa")
    fig.tight_layout()

    if export:
        Path("output").mkdir(exist_ok=True)
        fig.savefig("output/skill_by_type.png", dpi=150, bbox_inches="tight")
        print("[SAVED] output/skill_by_type.png")
    plt.show()


def chart_stack_segmentation(df_seg: pd.DataFrame, export: bool = False) -> None:
    """Horizontal bar chart — skill stack distribution."""
    fig, ax = plt.subplots(figsize=(10, 5))

    filtered = df_seg[df_seg["stack_type"] != "Other / No core skill"].copy()
    colors   = ["#2E86AB", "#E84855", "#3BB273", "#E9C46A", "#7B2D8B", "#F4A261"]

    bars = ax.barh(filtered["stack_type"], filtered["pct"],
                   color=colors[:len(filtered)], edgecolor="white")
    ax.bar_label(bars, fmt="%.1f%%", padding=4, fontsize=9)
    ax.set_xlabel("% of All Job Postings", fontsize=11)
    ax.set_title("Skill Stack Segmentation — What Combinations Do Jobs Require?",
                 fontsize=12, fontweight="bold")
    ax.invert_yaxis()
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_facecolor("#fafafa")
    fig.tight_layout()

    if export:
        Path("output").mkdir(exist_ok=True)
        fig.savefig("output/skill_stack.png", dpi=150, bbox_inches="tight")
        print("[SAVED] output/skill_stack.png")
    plt.show()


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Job Market Skill Demand Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python job_analysis.py
  python job_analysis.py --path data/job_data.csv
  python job_analysis.py --path data/job_data.csv --top 15 --export
        """,
    )
    parser.add_argument(
        "--path",
        default=DEFAULT_CSV,
        help=f"Path to job_data.csv (default: {DEFAULT_CSV})",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=12,
        help="Number of top skills to display in demand chart (default: 12)",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Save all charts as PNG files in output/ folder",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  JOB MARKET SKILL DEMAND ANALYSIS")
    print("  Dataset: LinkedIn Analyst Job Postings")
    print("=" * 60)

    # Load
    df = load_data(args.path)

    # Analyses
    dataset_summary(df)

    df_demand = overall_skill_demand(df, top_n=args.top)
    df_level  = skill_demand_by_level(df)
    df_type   = skill_demand_by_work_type(df)

    skill_demand_by_country(df)
    sql_cooccurrence(df)
    level_worktype_crosstab(df)
    df_seg = skill_stack_segmentation(df)

    business_insights(df)

    # Charts
    section("10. CHARTS")
    print("  Generating charts…")
    chart_overall_demand(df_demand, export=args.export)
    chart_by_level(df_level,        export=args.export)
    chart_by_type(df_type,          export=args.export)
    chart_stack_segmentation(df_seg, export=args.export)

    print("\n[DONE] Analysis complete.\n")


if __name__ == "__main__":
    main()