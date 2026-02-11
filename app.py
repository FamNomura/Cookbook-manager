import streamlit as st
from github import Github
from PIL import Image
import io
import datetime

# --- 設定 ---
st.set_page_config(page_title="レシピ投稿", page_icon="🍳")

# GitHubへの接続とカテゴリ取得
@st.cache_data(ttl=600)
def get_existing_categories():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            return []
            
        token = st.secrets["GITHUB_TOKEN"]
        repo_name = st.secrets["REPO_NAME"]
        g = Github(token)
        repo = g.get_repo(repo_name)
        
        contents = repo.get_git_tree("main", recursive=True).tree
        
        categories = set()
        for content in contents:
            if content.path.startswith("docs/") and content.type == "tree":
                cat_name = content.path.replace("docs/", "")
                if cat_name != "images" and not cat_name.startswith("."):
                    categories.add(cat_name)
        
        return sorted(list(categories))
    except Exception as e:
        return []

# テキスト整形関数
def format_ingredients(text):
    if not text: return ""
    lines = text.strip().split('\n')
    formatted = []
    for line in lines:
        line = line.strip()
        if line:
            formatted.append(f"* {line}")
    return "\n".join(formatted)

def format_steps(text):
    if not text: return ""
    lines = text.strip().split('\n')
    formatted = []
    for i, line in enumerate(lines):
        line = line.strip()
        if line:
            formatted.append(f"{i+1}. {line}")
    return "\n".join(formatted)

# --- UI構築 ---
st.title("🍳 レシピ投稿アプリ Ver.3.0")

# 1. カテゴリ選択（フォームの外に出しました）
# これで操作した瞬間に画面が反応します
st.subheader("① カテゴリを決める")
existing_cats = get_existing_categories()
cat_mode = st.radio("入力モード", ["既存から選ぶ", "新規作成する"], horizontal=True)

final_category = ""

if cat_mode == "既存から選ぶ":
    if existing_cats:
        final_category = st.selectbox("カテゴリ一覧", existing_cats)
    else:
        st.warning("カテゴリが見つかりません。新規作成してください。")
else:
    # 新規作成モード
    new_cat_input = st.text_input("新しいカテゴリ名", placeholder="例：調味料/自家製ダレ")
    final_category = new_cat_input

# 2. その他の入力（ここから下はフォームにします）
st.subheader("② レシピを入力する")

with st.form("recipe_form"):
    title = st.text_input("料理名", placeholder="例：豚の角煮")
    
    uploaded_file = st.file_uploader("料理の写真", type=['jpg', 'jpeg', 'png'])

    st.markdown("材料 (改行で区切る)")
    raw_ingredients = st.text_area("材料", height=150, label_visibility="collapsed")

    st.markdown("手順 (改行で区切る)")
    raw_steps = st.text_area("手順", height=150, label_visibility="collapsed")

    memo = st.text_area("メモ・ポイント")

    # フォームの送信ボタン
    submitted = st.form_submit_button("レシピを投稿する", type="primary")

# --- 送信処理 ---
if submitted:
    # フォームの外にある変数をここでチェックします
    if not title:
        st.error("エラー：料理名を入力してください")
    elif not final_category:
        st.error("エラー：カテゴリが入力されていません")
    else:
        try:
            with st.spinner("送信中..."):
                token = st.secrets["GITHUB_TOKEN"]
                repo_name = st.secrets["REPO_NAME"]
                g = Github(token)
                repo = g.get_repo(repo_name)

                # A. 画像処理
                image_path = ""
                if uploaded_file:
                    image = Image.open(uploaded_file)
                    max_size = 1200
                    if max(image.size) > max_size:
                        image.thumbnail((max_size, max_size))
                    
                    img_byte_arr = io.BytesIO()
                    if image.mode in ("RGBA", "P"): 
                        image = image.convert("RGB")
                    
                    image.save(img_byte_arr, format='JPEG', quality=80, optimize=True)
                    img_byte_arr = img_byte_arr.getvalue()
                    
                    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                    img_filename = f"img_{timestamp}.jpg"
                    
                    repo.create_file(
                        path=f"docs/images/{img_filename}",
                        message=f"Add image for {title}",
                        content=img_byte_arr
                    )
                    image_path = f"../images/{img_filename}"

                # B. テキスト整形
                formatted_ingredients = format_ingredients(raw_ingredients)
                formatted_steps = format_steps(raw_steps)

                md_content = f"# {title}\n\n"
                if image_path:
                    md_content += f"![{title}]({image_path})\n\n"
                
                md_content += f"## 材料\n{formatted_ingredients}\n\n"
                md_content += f"## 手順\n{formatted_steps}\n\n"
                if memo:
                    md_content += f"## メモ\n{memo}\n"

                # C. ファイル作成
                clean_category = final_category.strip().strip("/")
                file_path = f"docs/{clean_category}/{title}.md"
                
                repo.create_file(
                    path=file_path,
                    message=f"Add recipe: {title}",
                    content=md_content
                )
                
                st.cache_data.clear()
                st.balloons()
                st.success(f"投稿完了！\nカテゴリ: {clean_category}")

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
