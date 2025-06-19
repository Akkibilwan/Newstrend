import streamlit as st
from GoogleNews import GoogleNews
from keybert import KeyBERT
import requests
from datetime import datetime
import openai
from typing import List, Dict

st.set_page_config(page_title="News Virality Analyzer", layout="wide")
st.title("📰 News Virality Analyzer")

# -------------------- Sidebar Inputs --------------------
topic = st.sidebar.text_input("Enter a topic", value="technology")
run = st.sidebar.button("Run Virality Scan")

# -------------------- Loaders --------------------
@st.cache_resource
def load_keybert():
    return KeyBERT()

# -------------------- News Fetcher --------------------
@st.cache_data
def fetch_top_news(topic: str, limit: int = 5) -> List[str]:
    googlenews = GoogleNews(lang='en')
    googlenews.search(topic)
    articles = googlenews.result()
    seen = set()
    titles = []
    for a in articles:
        title = a['title'].strip()
        if title and title not in seen:
            seen.add(title)
            titles.append(title)
        if len(titles) == limit:
            break
    return titles

# -------------------- Keyphrase Extractor --------------------
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
            top_n=2
        )]
        result[title] = phrases
    return result

# -------------------- OpenAI-powered Virality Estimator --------------------
def estimate_virality_with_openai(phrase: str) -> Dict[str, int]:
    openai.api_key = st.secrets["OPENAI_API_KEY"]

    prompt = f"""
You are a social listening analyst. Based on public data, estimate the virality of the phrase below:

Phrase: "{phrase}"
Time window: last 4 days
Platforms: Twitter and Reddit

Return a JSON object like:
{{
  "twitter_score": 0–100 (based on impressions, tweet count, recency),
  "reddit_score": 0–100 (based on upvotes, post count, recency),
  "reason": "Brief explanation of why this score was given"
}}

Respond ONLY with the JSON object.
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=200
        )
        text = response.choices[0].message.content.strip()
        return eval(text) if text.startswith("{") else {"twitter_score": 0, "reddit_score": 0, "reason": "Parsing failed"}
    except Exception as e:
        st.warning(f"OpenAI error for '{phrase}': {e}")
        return {"twitter_score": 0, "reddit_score": 0, "reason": "API error"}

# -------------------- Scoring --------------------
def compute_virality(t_score: int, r_score: int) -> Dict:
    combined = round((t_score * 0.55) + (r_score * 0.35), 1)
    label = "🔴 Low"
    if t_score >= 80 or r_score >= 80:
        label = "🟢 High"
    elif (t_score >= 50 and r_score >= 50) or combined >= 60:
        label = "🟡 Medium"
    return {"score": combined, "label": label}

# -------------------- MAIN --------------------
if run:
    st.subheader("📰 Step 1: Fetching News...")
    headlines = fetch_top_news(topic)
    if not headlines:
        st.error("No news found.")
        st.stop()
    st.success(f"Fetched {len(headlines)} headlines")

    st.subheader("🔍 Step 2: Extracting Searchable Phrases...")
    kw_model = load_keybert()
    phrase_dict = extract_phrases(_kw_model=kw_model, headlines=headlines)

    st.subheader("🧠 Step 3: Estimating Virality with OpenAI")
    for title in headlines:
        phrases = phrase_dict.get(title, [])
        twitter_score = 0
        reddit_score = 0
        reason = "No signals detected"

        for phrase in phrases:
            result = estimate_virality_with_openai(phrase)
            twitter_score = max(twitter_score, result.get("twitter_score", 0))
            reddit_score = max(reddit_score, result.get("reddit_score", 0))
            reason = result.get("reason", "")

        final = compute_virality(twitter_score, reddit_score)

        with st.container():
            st.markdown(f"### 🗞️ {title}")
            st.markdown(f"**Key Phrases:** `{', '.join(phrases)}`")
            st.markdown(f"**Explanation:** {reason}")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="🐦 Twitter Score", value=twitter_score)
            with col2:
                st.metric(label="👽 Reddit Score", value=reddit_score)
            with col3:
                st.metric(label="🔥 Overall", value=final['label'])
            st.markdown("---")

    st.balloons()
