#!/usr/bin/env python3
"""
California Government Ballot Measures Scraper - Streamlit GUI
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import json
from pathlib import Path

def main():
    st.set_page_config(
        page_title="CA Gov Ballot Measures",
        page_icon="🗳️",
        layout="wide"
    )
    
    st.title("🗳️ California Government Ballot Measures Scraper")
    st.markdown("*Monitor ballot measures across California government*")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        level = st.selectbox(
            "Government Level",
            ["State", "County", "City", "All"]
        )
        
        if st.button("🚀 Run Scraper", type="primary"):
            with st.spinner("Scraping data..."):
                try:
                    from ..scrapers.state_scraper import CAStateScraper
                    
                    scraper = CAStateScraper()
                    results = scraper.scrape_all()
                    
                    st.session_state['results'] = results
                    st.success("✅ Scraping completed!")
                    
                except Exception as e:
                    st.error(f"❌ Error: {e}")
    
    # Main content
    if 'results' in st.session_state:
        results = st.session_state['results']
        
        st.subheader("📊 Results")
        st.metric("Measures Found", len(results.get('measures', [])))
        
        if results.get('measures'):
            df = pd.DataFrame(results['measures'])
            st.dataframe(df, use_container_width=True)
            
            # Download button
            st.download_button(
                "📥 Download JSON",
                data=json.dumps(results, indent=2),
                file_name=f"ballot_measures_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json"
            )
    else:
        st.info("👆 Configure settings in the sidebar and click 'Run Scraper' to begin")
        
        # Show some example data or status
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Counties", "58")
        with col2:
            st.metric("Cities", "482")
        with col3:
            st.metric("Special Districts", "2,949")

if __name__ == "__main__":
    main()
