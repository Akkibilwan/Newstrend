import streamlit as st
from GoogleNews import GoogleNews
from keybert import KeyBERT
import requests
from datetime import datetime
from openai import OpenAI
from typing import List, Dict

st.set_page_config(page_title="News Virality Analyzer", layout="wide")
st.title("📰 News Virality Analyzer")

# -------------------- Sidebar Inputs --------------------
topic = st.sidebar.text_input("Enter a topic", value="technology")
num_articles = st.sidebar.slider("How many news articles?", 1, 10, 5)
run = st.sidebar.button("Run Virality Scan")

# -------------------- Loaders --------------------
@st.cache_resource
def load_keybert():
    return KeyBERT()

@st.cache_resource
def openai_client():
    return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# -------------------- News Fetcher --------------------
@st.cache_data
def fetch_top_news(topic: str, limit: int) -> List[str]:
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
    return titles, len(articles)

# -------------------- Phrase Generator --------------------
def generate_phrases_from_openai(title: str) -> List[str]:
    client = openai_client()
    prompt = f"""
You are an SEO assistant. Given the following news headline, extract 2-3 highly searchable and socially relevant key phrases (2 to 6 words each) that someone might search on Twitter or Reddit:

Headline: "{title}"

Respond ONLY as a JSON list of strings.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150
        )
        reply = response.choices[0].message.content.strip()
        return eval(reply) if reply.startswith("[") else []
    except:
        return []

# -------------------- Reddit Real Search --------------------
def fetch_reddit_posts(phrase: str, max_results: int = 5) -> List[Dict]:
    headers = {"User-Agent": "Mozilla/5.0"}
    url = f"https://www.reddit.com/search.json?q={requests.utils.quote(phrase)}&limit={max_results}&sort=new"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        posts = response.json().get("data", {}).get("children", [])
        result = []
        for post in posts:
            data = post.get("data", {})
            created_utc = datetime.utcfromtimestamp(data.get("created_utc", 0))
            if (datetime.utcnow() - created_utc).days <= 4:
                result.append({
                    "title": data.get("title", ""),
                    "subreddit": data.get("subreddit", ""),
                    "upvotes": data.get("score", 0),
                    "url": "https://reddit.com" + data.get("permalink", "")
                })
        return result
    except:
        return []

# -------------------- Twitter Mock (OpenAI-Driven) --------------------
def fetch_twitter_sources(phrase: str) -> List[Dict]:
    client = openai_client()
    prompt = f"""
Based on current social activity, simulate 2-3 example Twitter posts containing this phrase: "{phrase}".
For each example, estimate an impression count between 0 and 100,000+.
Respond in this JSON format:
[
  {"text": "tweet content", "impressions": 54200},
  ...
]
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=200
        )
        reply = response.choices[0].message.content.strip()
        return eval(reply) if reply.startswith("[") else []
    except:
        return []

# -------------------- Virality Score Calculation --------------------
def compute_virality(twitter_posts: List[Dict], reddit_posts: List[Dict]) -> Dict:
    twitter_score = 0
    reddit_score = 0

    for tweet in twitter_posts:
        if tweet.get("impressions", 0) > 50000:
            twitter_score += 30
    twitter_score = min(twitter_score, 100)

    for post in reddit_posts:
        if post.get("upvotes", 0) > 2000:
            reddit_score += 35
    reddit_score = min(reddit_score, 100)

    combined_score = round((twitter_score * 0.55) + (reddit_score * 0.35) + 10, 1)

    if twitter_score >= 80 or reddit_score >= 80:
        label = "🟢 High"
    elif twitter_score >= 50 or reddit_score >= 50:
        label = "🟡 Medium"
    else:
        label = "🔴 Low"

    return {
        "twitter_score": twitter_score,
        "reddit_score": reddit_score,
        "combined": combined_score,
        "label": label
    }

# -------------------- MAIN --------------------
if run:
    st.subheader("📰 Step 1: Fetching News...")
    headlines, total_found = fetch_top_news(topic, num_articles)
    st.success(f"Fetched {len(headlines)} of {total_found} found")

    st.subheader("🔍 Step 2: Extracting Key Phrases via OpenAI")
    phrase_dict = {}
    for title in headlines:
        phrases = generate_phrases_from_openai(title)
        phrase_dict[title] = phrases

    st.subheader("📊 Step 3: Evaluating Virality and Sources")
    for title in headlines:
        phrases = phrase_dict.get(title, [])
        twitter_all = []
        reddit_all = []

        for phrase in phrases:
            twitter_posts = fetch_twitter_sources(phrase)
            reddit_posts = fetch_reddit_posts(phrase)
            twitter_all.extend(twitter_posts)
            reddit_all.extend(reddit_posts)

        result = compute_virality(twitter_all, reddit_all)

        with st.container():
            st.markdown(f"### 🗞️ {title}")
            st.markdown(f"**Key Phrases:** `{', '.join(phrases)}`")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="🐦 Twitter Score", value=result['twitter_score'])
            with col2:
                st.metric(label="👽 Reddit Score", value=result['reddit_score'])
            with col3:
                st.metric(label="🔥 Overall", value=result['combined'])
            st.markdown(f"**Final Verdict:** {result['label']}")

            if twitter_all:
                with st.expander("🔗 Twitter Examples"):
                    for tweet in twitter_all:
                        st.markdown(f"- {tweet['text']} — 👁 {tweet['impressions']} views")

            if reddit_all:
                with st.expander("🔗 Reddit Posts"):
                    for post in reddit_all:
                        st.markdown(f"- [{post['title']}]({post['url']}) — 🔼 {post['upvotes']} (r/{post['subreddit']})")
            st.markdown("---")

    st.balloons()
