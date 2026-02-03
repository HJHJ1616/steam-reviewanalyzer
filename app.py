import streamlit as st
import requests
import google.generativeai as genai
import time

# 1. 페이지 설정
st.set_page_config(page_title="Steam Review Analyzer (Global)", page_icon="🎮", layout="wide")
st.title("🎮 Steam 리뷰 심층 분석기 (Global Ver.)")
st.markdown("""
App ID만 입력하면 **유저 피드백과 개선점**을 심층 분석합니다.
Select language in the sidebar to change the report language.
""")

# ==========================================
# 2. 사이드바 설정 (언어 선택 기능 추가!)
# ==========================================
with st.sidebar:
    st.header("⚙️ Settings")
    
    # 🌍 언어 선택 버튼 (여기가 핵심!)
    report_lang = st.radio(
        "Report Language / 분석 언어",
        ["🇰🇷 한국어", "🇺🇸 English"],
        index=0
    )
    
    st.divider()

    # API 키 처리
    api_key = None
    try:
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success(f"✅ API Key Loaded ({report_lang})")
    except:
        pass

    if not api_key:
        api_key = st.text_input("Gemini API Key", type="password")
        if not api_key:
            st.warning("Please enter API Key first.")
    
    target_count = st.slider("Review Count / 분석 개수", 50, 500, 200)

# 3. 데이터 수집 함수 (기존과 동일)
def collect_reviews(app_id, target_count):
    reviews = []
    cursor = '*'
    params = {'json': 1, 'filter': 'updated', 'language': 'all', 'num_per_page': 100}
    
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    while len(reviews) < target_count:
        params['cursor'] = cursor
        try:
            response = requests.get(f"https://store.steampowered.com/appreviews/{app_id}", params=params, timeout=10)
            data = response.json()
        except:
            break
            
        if 'reviews' not in data or not data['reviews']: break

        for review in data['reviews']:
            content = review['review'].replace("\n", " ").strip()
            if len(content) < 30: continue 
            
            playtime = int(review['author']['playtime_forever']/60)
            vote = 'Recommended' if review['voted_up'] else 'Not Recommended'
            reviews.append(f"[{playtime}h] {vote}: {content}")
            
            current_len = len(reviews)
            status_text.text(f"🔍 Collecting... {current_len} reviews")
            progress_bar.progress(min(current_len / target_count, 1.0))
            
            if current_len >= target_count: break
        
        cursor = data.get('cursor')
        if not cursor: break
    
    status_text.empty()
    progress_bar.empty()
    return reviews

# 4. AI 분석 함수 (언어에 따라 프롬프트 자동 변경)
def analyze_gemini(api_key, reviews, lang_option):
    genai.configure(api_key=api_key)
    
    # 모델 자동 선택
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
    except:
        return "❌ Error: API Key is invalid."

    target_model = ""
    if 'models/gemini-1.5-flash' in available_models: target_model = 'gemini-1.5-flash'
    elif 'models/gemini-pro' in available_models: target_model = 'gemini-pro'
    elif available_models: target_model = available_models[0].replace('models/', '')
    else: return "❌ No available models found."

    model = genai.GenerativeModel(target_model)
    full_text = "\n".join(reviews)
    
    # 🇰🇷 한국어 프롬프트
    prompt_kr = f"""
    너는 글로벌 게임사의 시니어 UX 리서처이자 제품 전략가야. 
    아래 Steam 리뷰 데이터를 분석하여 '제품 개선을 위한 핵심 지표'를 도출해줘.

    [분석 가이드라인]
    1. 언어 통합: 리뷰 원문 언어와 상관없이 내용을 통합하여 분석할 것.
    2. 경쟁작 비교: 다른 게임과 비교하는 내용을 반드시 찾아서 인용할 것.
    3. 개선 제안 (IF 분석): "~하면 좋을 텐데" 같은 유저의 아쉬움과 제안을 시스템적으로 정리할 것.

    [결과 리포트 양식]
    1. 🔍 **경쟁사 대비 비교 분석**: 타 게임 언급 사례 및 우위/열위 포인트.
    2. 💡 **구체적 개선 제안 TOP 3**: 유저들이 가장 원하는 기능/시스템 변경사항.
    3. 📉 **치명적 이탈 요인 (Pain Points)**:
