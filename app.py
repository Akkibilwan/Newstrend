# app.py

import streamlit as st
from GoogleNews import GoogleNews
from keybert import KeyBERT
from typing import List, Dict

st.set_page_config(page_title="News Virality Analyzer", layout="wide")
st.title("📰 News Virality Analyzer")

# -------------------- Sidebar Inputs --------------------
topic = st.sidebar.text_input("Enter a topic", value="technology")
run = st.sidebar.button("Analyze Virality")

# -------------------- Helper Functions --------------------

@st.cache_resource
def load_keybert():
    return KeyBERT()

@st.cache_data(show_spinner=False)
def fetch_top_news(topic: str, num_articles: int = 10) -> List[str]:
    googlenews = GoogleNews(lang='en')
    googlenews.search(topic)
    articles = googlenews.result()
    seen = set()
    unique_titles = []
    for a in articles:
        title = a['title']
        if title not in seen and title.strip() != "":
            seen.add(title)
            unique_titles.append(title)
        if len(unique_titles) == 5:
            break
    return unique_titles

@st.cache_data
def extract_phrases(_kw_model, headlines: List[str]) -> Dict[str, List[str]]:
    result = {}
    for title in headlines:
        phrases = [kw[0] for kw in _kw_model.extract_keywords(
            title,
            keyphrase_ngram_range=(2, 4),
            stop_words='english',
            use_mmr=True,
            diversity=0.7,
            top_n=3
        )]
        result[title] = phrases
    return result

# -------------------- Main App Logic --------------------
if run:
    st.subheader("🔍 Fetching Top 5 News Headlines...")
    headlines = fetch_top_news(topic)
    if not headlines:
        st.error("No news found.")
        st.stop()
    st.success(f"Fetched {len(headlines)} unique news items.")

    st.subheader("🧠 Extracting Searchable Keyphrases...")
    kw_model = load_keybert()
    phrase_dict = extract_phrases(_kw_model=kw_model, headlines=headlines)

    with st.expander("📋 Headlines & Phrases", expanded=True):
        for title, phrases in phrase_dict.items():
            st.markdown(f"**📰 {title}**")
            st.markdown(f"`Key Phrases:` {', '.join(phrases)}`")
            st.markdown("---")

    st.info("✅ Next: We will fetch Twitter + Reddit data and compute virality scores.")
