import streamlit as st
import requests
import google.generativeai as genai
import time

# 1. 페이지 설정
st.set_page_config(page_title="Steam 리뷰 분석기", page_icon="🎮", layout="wide")
st.title("🎮 Steam 리뷰 심층 분석기 (Web Ver.)")
st.markdown("App ID만 입력하면 **플레이 타임별 유저 반응**을 분석해드립니다.")

# 2. 사이드바 설정 (자동/수동 로그인 통합)
with st.sidebar:
    st.header("⚙️ 설정")
    api_key = None
    
    # secrets 파일이 있으면 자동으로 가져오고, 없으면 그냥 넘어감 (오류 방지)
    try:
        if "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
            st.success("✅ API 키 자동 연동됨")
    except:
        pass

    # 연동 안 됐으면 직접 입력받기
    if not api_key:
        api_key = st.text_input("Gemini API Key", type="password")
        if not api_key:
            st.warning("👈 먼저 API 키를 입력해주세요!")
    
    target_count = st.slider("분석 리뷰 수", 50, 500, 200)

# 3. 데이터 수집 함수
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
            vote = '추천' if review['voted_up'] else '비추천'
            reviews.append(f"[{playtime}h] {vote}: {content}")
            
            # 진행률 표시
            current_len = len(reviews)
            status_text.text(f"🔍 {current_len}개 확보 중...")
            progress_bar.progress(min(current_len / target_count, 1.0))
            
            if current_len >= target_count: break
        
        cursor = data.get('cursor')
        if not cursor: break
    
    status_text.empty()
    progress_bar.empty()
    return reviews

# 4. AI 분석 함수 (모델 자동 선택)
def analyze_gemini(api_key, reviews):
    genai.configure(api_key=api_key)
    
    # 사용 가능한 모델 찾기
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
    except:
        return "❌ API 키가 올바르지 않거나 권한이 없습니다."

    # 모델 우선순위 선택
    target_model = ""
    if 'models/gemini-1.5-flash' in available_models: target_model = 'gemini-1.5-flash'
    elif 'models/gemini-pro' in available_models: target_model = 'gemini-pro'
    elif available_models: target_model = available_models[0].replace('models/', '')
    else: return "❌ 사용 가능한 모델이 없습니다."

    model = genai.GenerativeModel(target_model)
    prompt = f"다음 스팀 리뷰를 플레이 타임별(초반/중반/고인물)로 상세 분석해줘:\n\n" + "\n".join(reviews)
    return model.generate_content(prompt).text

# ==========================================
# 5. 메인 실행 화면 (여기가 중요합니다!!)
# ==========================================
st.divider() # 구분선

# 👇 여기가 입력칸입니다!
app_id = st.text_input("Steam App ID 입력 (예: 413150)", placeholder="숫자만 입력하세요")

# 👇 여기가 버튼입니다!
if st.button("🚀 분석 시작", type="primary", use_container_width=True):
    if not api_key:
        st.error("⚠️ 왼쪽 사이드바에 API 키를 먼저 입력해주세요!")
    elif not app_id:
        st.warning("⚠️ App ID를 입력해주세요.")
    else:
        with st.spinner("데이터 수집 및 AI 분석 중..."):
            data_list = collect_reviews(app_id, target_count)
            if data_list:
                report = analyze_gemini(api_key, data_list)
                st.markdown("---")
                st.subheader("📊 분석 리포트")
                st.write(report)
                
                # 다운로드 버튼
                st.download_button("💾 결과 다운로드", report, f"Report_{app_id}.txt")
            else:
                st.error("리뷰를 찾을 수 없습니다. App ID를 확인해주세요.")