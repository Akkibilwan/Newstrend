import platform
import streamlit as st
st.info(f"Running on Python {platform.python_version()}")

import streamlit as st
from GoogleNews import GoogleNews
from keybert import KeyBERT
import snscrape.modules.twitter as sntwitter
import requests
from datetime import datetime, timedelta
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
            top_n=3
        )]
        result[title] = phrases
    return result

# -------------------- Twitter Search --------------------
def check_twitter_virality(phrase: str) -> int:
    count = 0
    threshold = 50000  # impressions
    now = datetime.utcnow()
    min_date = now - timedelta(days=4)
    try:
        for tweet in sntwitter.TwitterSearchScraper(f'{phrase} since:{min_date.date()}').get_items():
            if hasattr(tweet, 'viewCount') and tweet.viewCount and tweet.viewCount > threshold:
                count += 1
            if count >= 3:
                break
    except:
        return 0
    return min(count * 30, 100)  # max 90 from Twitter

# -------------------- Reddit Search --------------------
def check_reddit_virality(phrase: str) -> int:
    try:
        url = f"https://www.reddit.com/search.json?q={requests.utils.quote(phrase)}&limit=10&sort=new"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        posts = resp.json().get("data", {}).get("children", [])
        score = 0
        for post in posts:
            data = post.get("data", {})
            created_utc = datetime.utcfromtimestamp(data.get("created_utc", 0))
            if (datetime.utcnow() - created_utc).days <= 4:
                if data.get("score", 0) > 2000:
                    score += 1
        return min(score * 35, 100)  # max 100 from Reddit
    except:
        return 0

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

    st.subheader("🔍 Step 2: Extracting Phrases...")
    kw_model = load_keybert()
    phrase_dict = extract_phrases(_kw_model=kw_model, headlines=headlines)

    st.subheader("📊 Step 3: Computing Virality...")
    for title in headlines:
        phrases = phrase_dict.get(title, [])
        twitter_score = 0
        reddit_score = 0

        for phrase in phrases:
            twitter_score = max(twitter_score, check_twitter_virality(phrase))
            reddit_score = max(reddit_score, check_reddit_virality(phrase))

        result = compute_virality(twitter_score, reddit_score)

        with st.container():
            st.markdown(f"### 🗞️ {title}")
            st.markdown(f"**Key Phrases:** `{', '.join(phrases)}`")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="🐦 Twitter Score", value=twitter_score)
            with col2:
                st.metric(label="👽 Reddit Score", value=reddit_score)
            with col3:
                st.metric(label="🔥 Overall", value=result['label'])
            st.markdown("---")

    st.balloons()
