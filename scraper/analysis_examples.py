#!/usr/bin/env python3
"""
Example Analysis Scripts for California Ballot Measures Database
Shows how to perform common analyses using Python, with R examples in comments
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Database connection
DB_PATH = "data/ballot_measures.db"

def get_connection():
    """Get database connection"""
    return sqlite3.connect(DB_PATH)

# ==============================================================================
# EXAMPLE 1: Historical Pass Rates by Decade
# ==============================================================================

def analyze_pass_rates_by_decade():
    """Analyze how pass rates have changed over time"""
    print("📊 Analyzing Pass Rates by Decade\n")
    
    query = """
    SELECT 
        decade,
        COUNT(*) as total_measures,
        SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed,
        SUM(CASE WHEN passed = 0 THEN 1 ELSE 0 END) as failed,
        ROUND(AVG(CASE WHEN passed IS NOT NULL THEN passed END) * 100, 1) as pass_rate
    FROM measures
    WHERE decade IS NOT NULL AND passed IS NOT NULL
    GROUP BY decade
    ORDER BY decade
    """
    
    df = pd.read_sql_query(query, get_connection())
    
    # Print summary
    print(df.to_string(index=False))
    
    # Plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    
    # Pass rate over time
    ax1.plot(df['decade'], df['pass_rate'], 'bo-', linewidth=2, markersize=8)
    ax1.set_xlabel('Decade')
    ax1.set_ylabel('Pass Rate (%)')
    ax1.set_title('California Ballot Measure Pass Rates by Decade')
    ax1.grid(True, alpha=0.3)
    
    # Number of measures over time
    ax2.bar(df['decade'], df['total_measures'], color='steelblue', alpha=0.7)
    ax2.set_xlabel('Decade')
    ax2.set_ylabel('Number of Measures')
    ax2.set_title('Volume of Ballot Measures by Decade')
    
    plt.tight_layout()
    plt.savefig('data/pass_rates_by_decade.png')
    print("\n💾 Saved plot: data/pass_rates_by_decade.png")
    
    """
    # R equivalent:
    library(DBI)
    library(ggplot2)
    
    con <- dbConnect(RSQLite::SQLite(), "data/ballot_measures.db")
    
    df <- dbGetQuery(con, "
        SELECT decade, 
               COUNT(*) as total_measures,
               ROUND(AVG(CASE WHEN passed IS NOT NULL THEN passed END) * 100, 1) as pass_rate
        FROM measures
        WHERE decade IS NOT NULL
        GROUP BY decade
        ORDER BY decade
    ")
    
    ggplot(df, aes(x = decade, y = pass_rate)) +
        geom_line(size = 1.5) +
        geom_point(size = 3) +
        theme_minimal() +
        labs(title = "Pass Rates by Decade", x = "Decade", y = "Pass Rate (%)")
    """

# ==============================================================================
# EXAMPLE 2: Topic Analysis
# ==============================================================================

def analyze_topics():
    """Analyze ballot measures by topic"""
    print("\n📊 Analyzing Measures by Topic\n")
    
    query = """
    SELECT 
        topic_primary,
        COUNT(*) as total,
        SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed,
        ROUND(AVG(CASE WHEN passed IS NOT NULL THEN passed END) * 100, 1) as pass_rate,
        MIN(year) as first_year,
        MAX(year) as last_year
    FROM measures
    WHERE topic_primary IS NOT NULL
    GROUP BY topic_primary
    HAVING total >= 5  -- Only topics with 5+ measures
    ORDER BY total DESC
    LIMIT 15
    """
    
    df = pd.read_sql_query(query, get_connection())
    
    # Create visualization
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Create horizontal bar chart
    y_pos = range(len(df))
    bars = ax.barh(y_pos, df['total'], color='steelblue', alpha=0.7)
    
    # Add pass rate as text
    for i, (total, pass_rate) in enumerate(zip(df['total'], df['pass_rate'])):
        if pd.notna(pass_rate):
            ax.text(total + 1, i, f'{pass_rate:.0f}%', va='center')
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(df['topic_primary'])
    ax.set_xlabel('Number of Measures')
    ax.set_title('Top 15 Ballot Measure Topics (with pass rates)')
    ax.grid(True, axis='x', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('data/topics_analysis.png')
    print("💾 Saved plot: data/topics_analysis.png")
    
    # Print summary table
    print("\nTop Topics Summary:")
    print(df[['topic_primary', 'total', 'pass_rate', 'first_year', 'last_year']].to_string(index=False))

# ==============================================================================
# EXAMPLE 3: Election Type Analysis
# ==============================================================================

def analyze_election_types():
    """Compare measures in different election types"""
    print("\n📊 Analyzing by Election Type\n")
    
    query = """
    SELECT 
        CASE 
            WHEN election_type IS NULL THEN 'Unknown'
            ELSE election_type
        END as election_type,
        COUNT(*) as total,
        AVG(percent_yes) as avg_yes_vote,
        SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) * 100.0 / 
            COUNT(CASE WHEN passed IS NOT NULL THEN 1 END) as pass_rate
    FROM measures
    GROUP BY election_type
    """
    
    df = pd.read_sql_query(query, get_connection())
    print(df.to_string(index=False))

# ==============================================================================
# EXAMPLE 4: Voter Sentiment Over Time
# ==============================================================================

def analyze_voter_sentiment():
    """Analyze average yes vote percentage over time"""
    print("\n📊 Analyzing Voter Sentiment Over Time\n")
    
    query = """
    SELECT 
        year,
        COUNT(*) as num_measures,
        ROUND(AVG(percent_yes), 1) as avg_yes_vote,
        ROUND(MIN(percent_yes), 1) as min_yes_vote,
        ROUND(MAX(percent_yes), 1) as max_yes_vote
    FROM measures
    WHERE percent_yes IS NOT NULL AND year >= 1950
    GROUP BY year
    HAVING num_measures >= 2  -- Years with multiple measures
    ORDER BY year
    """
    
    df = pd.read_sql_query(query, get_connection())
    
    # Create plot with confidence bands
    fig, ax = plt.subplots(figsize=(14, 6))
    
    ax.plot(df['year'], df['avg_yes_vote'], 'b-', linewidth=2, label='Average Yes %')
    ax.fill_between(df['year'], df['min_yes_vote'], df['max_yes_vote'], 
                    alpha=0.2, color='blue', label='Min-Max Range')
    ax.axhline(y=50, color='red', linestyle='--', alpha=0.5, label='50% Threshold')
    
    ax.set_xlabel('Year')
    ax.set_ylabel('Yes Vote %')
    ax.set_title('Voter Sentiment on Ballot Measures Over Time (1950-Present)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('data/voter_sentiment.png')
    print("💾 Saved plot: data/voter_sentiment.png")

# ==============================================================================
# EXAMPLE 5: Data Quality Report
# ==============================================================================

def data_quality_report():
    """Generate a data quality report"""
    print("\n📊 Data Quality Report\n")
    
    query = """
    SELECT * FROM data_quality
    """
    
    df = pd.read_sql_query(query, get_connection())
    
    # Calculate percentages
    for col in ['has_title', 'has_description', 'has_vote_data', 'has_outcome', 'has_pdf']:
        df[f'{col}_pct'] = round(df[col] / df['total_records'] * 100, 1)
    
    print("Data Completeness by Source:")
    print("-" * 80)
    for _, row in df.iterrows():
        print(f"\n{row['data_source']}:")
        print(f"  Total Records: {row['total_records']}")
        print(f"  Has Title: {row['has_title_pct']}%")
        print(f"  Has Description: {row['has_description_pct']}%")
        print(f"  Has Vote Data: {row['has_vote_data_pct']}%")
        print(f"  Has Outcome: {row['has_outcome_pct']}%")
        print(f"  Has PDF Link: {row['has_pdf_pct']}%")

# ==============================================================================
# EXAMPLE 6: Initiative vs Referendum Analysis
# ==============================================================================

def analyze_measure_types():
    """Compare different types of ballot measures"""
    print("\n📊 Analyzing Measure Types\n")
    
    query = """
    SELECT 
        CASE 
            WHEN measure_type LIKE '%initiative%' THEN 'Initiative'
            WHEN measure_type LIKE '%referendum%' THEN 'Referendum'
            WHEN measure_type LIKE '%amendment%' THEN 'Amendment'
            WHEN measure_type IS NULL THEN 'Unknown'
            ELSE 'Other'
        END as measure_category,
        COUNT(*) as total,
        SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed,
        ROUND(AVG(percent_yes), 1) as avg_yes_vote
    FROM measures
    GROUP BY measure_category
    ORDER BY total DESC
    """
    
    df = pd.read_sql_query(query, get_connection())
    
    # Calculate pass rate
    df['pass_rate'] = round(df['passed'] / df['total'] * 100, 1)
    
    print(df.to_string(index=False))
    
    # Create comparison chart
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # Pass rates by type
    ax1.bar(df['measure_category'], df['pass_rate'], color='green', alpha=0.7)
    ax1.set_ylabel('Pass Rate (%)')
    ax1.set_title('Pass Rates by Measure Type')
    ax1.tick_params(axis='x', rotation=45)
    
    # Average yes vote by type
    ax2.bar(df['measure_category'], df['avg_yes_vote'], color='blue', alpha=0.7)
    ax2.set_ylabel('Average Yes Vote (%)')
    ax2.set_title('Average Support by Measure Type')
    ax2.tick_params(axis='x', rotation=45)
    ax2.axhline(y=50, color='red', linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    plt.savefig('data/measure_types_analysis.png')
    print("\n💾 Saved plot: data/measure_types_analysis.png")

# ==============================================================================
# Main execution
# ==============================================================================

def main():
    """Run all analyses"""
    print("🔍 California Ballot Measures - Analysis Examples")
    print("=" * 60)
    
    # Check if database exists
    if not Path(DB_PATH).exists():
        print("❌ Database not found. Run setup_ballot_database.py first!")
        return
    
    # Run analyses
    analyze_pass_rates_by_decade()
    analyze_topics()
    analyze_election_types()
    analyze_voter_sentiment()
    data_quality_report()
    analyze_measure_types()
    
    print("\n✅ All analyses complete!")
    print("📁 Results saved in data/ directory")
    
    # Create SQL query examples file
    with open('data/example_queries.sql', 'w') as f:
        f.write("""-- California Ballot Measures - Example SQL Queries

-- 1. Find all tax-related measures that passed
SELECT year, title, percent_yes
FROM measures
WHERE (topic_primary LIKE '%tax%' OR title LIKE '%tax%')
  AND passed = 1
ORDER BY year DESC;

-- 2. Compare pass rates between different eras
SELECT 
    CASE 
        WHEN year < 1950 THEN 'Pre-1950'
        WHEN year < 1980 THEN '1950-1979'
        WHEN year < 2000 THEN '1980-1999'
        ELSE '2000-Present'
    END as era,
    COUNT(*) as total,
    ROUND(AVG(passed) * 100, 1) as pass_rate
FROM measures
WHERE passed IS NOT NULL
GROUP BY era
ORDER BY era;

-- 3. Find controversial measures (close votes)
SELECT year, title, percent_yes
FROM measures
WHERE percent_yes BETWEEN 45 AND 55
  AND percent_yes IS NOT NULL
ORDER BY ABS(percent_yes - 50), year DESC;

-- 4. Measures with summaries
SELECT year, title, summary_title, summary_text
FROM measures
WHERE has_summary = 1
ORDER BY year DESC;

-- 5. Most active years
SELECT year, COUNT(*) as num_measures
FROM measures
GROUP BY year
HAVING num_measures >= 5
ORDER BY num_measures DESC, year DESC;
""")
    
    print("\n📝 SQL query examples saved to: data/example_queries.sql")

if __name__ == "__main__":
    # Set up plotting style
    plt.style.use('seaborn-v0_8-darkgrid')
    sns.set_palette("husl")
    
    main()