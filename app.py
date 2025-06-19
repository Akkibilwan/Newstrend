# app.py

import streamlit as st
import requests
from GoogleNews import GoogleNews
from keybert import KeyBERT
from typing import List, Dict

# -------------------- Streamlit Config --------------------
st.set_page_config(page_title="Social Signal Bot", layout="wide")
st.title("📡 Social Signal Bot")

# -------------------- Sidebar Inputs --------------------
st.sidebar.header("Configuration")
topic = st.sidebar.text_input("Enter a news topic", value="technology")
num_articles = st.sidebar.slider("Number of news articles", 1, 10, 5)
run = st.sidebar.button("Run Bot")

# -------------------- Caching Utilities --------------------
@st.cache_data(show_spinner=False)
def fetch_news(topic: str, count: int) -> List[str]:
    googlenews = GoogleNews(lang='en')
    googlenews.search(topic)
    articles = googlenews.result()[:count]
    return [a['title'] for a in articles]

@st.cache_resource
def get_kw_model():
    return KeyBERT()

@st.cache_data
def extract_keywords(_kw_model, texts: List[str], top_n: int = 5) -> Dict[str, List[str]]:
    keywords_dict = {}
    for title in texts:
        phrases = [kw[0] for kw in _kw_model.extract_keywords(
            title,
            keyphrase_ngram_range=(2, 4),     # ✅ longer, meaningful phrases
            stop_words='english',
            use_mmr=True,                     # ✅ better diversity & relevance
            diversity=0.7,
            top_n=top_n
        )]
        keywords_dict[title] = phrases
    return keywords_dict

@st.cache_data
def scrape_reddit(keyword: str, max_results: int = 5) -> List[Dict[str, str]]:
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://www.reddit.com/search.json?q={requests.utils.quote(keyword)}&limit={max_results}&sort=new"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        posts = []
        if response.status_code == 200:
            for post in response.json().get("data", {}).get("children", []):
                data = post.get("data", {})
                posts.append({
                    "title": data.get("title", ""),
                    "subreddit": data.get("subreddit", "")
                })
        return posts
    except Exception as e:
        st.warning(f"⚠️ Reddit error for '{keyword}': {e}")
        return []

def safe_scrape_tweets(keyword: str, max_results: int = 5) -> List[Dict[str, str]]:
    try:
        import snscrape.modules.twitter as sntwitter
        tweets = []
        for i, tweet in enumerate(sntwitter.TwitterSearchScraper(f'{keyword} lang:en').get_items()):
            if i >= max_results:
                break
            tweets.append({
                "username": tweet.user.username,
                "content": tweet.content
            })
        return tweets
    except Exception as e:
        st.warning(f"⚠️ Twitter error for '{keyword}': {e}")
        return []

# -------------------- Main Execution --------------------
if run:
    st.subheader("🔍 Fetching News")
    headlines = fetch_news(topic, num_articles)
    if not headlines:
        st.error("No headlines found.")
        st.stop()
    st.success(f"Fetched {len(headlines)} headlines")

    st.subheader("🧠 Extracting Searchable Phrases")
    kw_model = get_kw_model()
    keywords_dict = extract_keywords(_kw_model=kw_model, texts=headlines)
    all_phrases = list({phrase for phrases in keywords_dict.values() for phrase in phrases})
    st.success(f"Extracted {len(all_phrases)} unique phrases")

    with st.expander("📰 Headlines & Key Phrases", expanded=True):
        for title, phrases in keywords_dict.items():
            st.markdown(f"**Headline:** {title}")
            st.markdown(f"`Phrases:` {', '.join(phrases)}`")
            st.markdown("---")

    st.subheader("📲 Social Signals")

    tabs = st.tabs(["Twitter", "Reddit"])

    with tabs[0]:
        for phrase in all_phrases:
            with st.expander(f"🐦 Tweets for: {phrase}"):
                tweets = safe_scrape_tweets(phrase)
                if not tweets:
                    st.info("No tweets found.")
                    continue
                for t in tweets:
                    st.markdown(f"- **@{t['username']}**: {t['content']}")

    with tabs[1]:
        for phrase in all_phrases:
            with st.expander(f"👽 Reddit Posts for: {phrase}"):
                posts = scrape_reddit(phrase)
                if not posts:
                    st.info("No Reddit posts found.")
                    continue
                for p in posts:
                    st.markdown(f"- [{p['title']}] - r/{p['subreddit']}")

    st.balloons()
