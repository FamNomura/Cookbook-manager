import streamlit as st
from github import Github
from PIL import Image
import io
import datetime

# --- 設定: カテゴリのリスト ---
# ここを書き換えれば、選択肢が増えます
CATEGORIES = {
    "主菜/肉料理": "主菜/肉料理",
    "主菜/魚料理": "主菜/魚料理",
    "副菜/サラダ": "副菜/サラダ",
    "副菜/スープ": "副菜/スープ",
    "主食/ご飯麺": "主食/ご飯麺",
    "デザート": "デザート",
}

st.title("🍳 レシピ投稿アプリ")

# --- 入力フォーム ---
with st.form("recipe_form"):
    title = st.text_input("料理名", placeholder="例：豚の角煮")
    category_key = st.selectbox("カテゴリ", list(CATEGORIES.keys()))
    
    # 画像アップロード
    uploaded_file = st.file_uploader("料理の写真", type=['jpg', 'jpeg', 'png'])
    
    ingredients = st.text_area("材料 (箇条書きで)", placeholder="* 豚肉: 200g\n* 玉ねぎ: 1個", height=150)
    steps = st.text_area("手順 (番号付きリストで)", placeholder="1. 肉を切る。\n2. 焼く。", height=150)
    memo = st.text_area("メモ・ポイント", placeholder="* 強火で一気に！")

    submitted = st.form_submit_button("レシピを投稿する")

# --- 送信処理 ---
if submitted:
    if not title:
        st.error("料理名を入力してください！")
    else:
        try:
            # 1. GitHubへの接続
            # StreamlitのSecretsからトークンを取得
            token = st.secrets["GITHUB_TOKEN"]
            repo_name = st.secrets["REPO_NAME"] # 例: yourname/my-recipe-site
            
            g = Github(token)
            repo = g.get_repo(repo_name)
            
            # 2. 画像の処理とアップロード
            image_path = ""
            if uploaded_file:
                image = Image.open(uploaded_file)
                
                # 画像のリサイズ (長辺を1000pxに縮小)
                max_size = 1000
                if max(image.size) > max_size:
                    image.thumbnail((max_size, max_size))
                
                # 画像をバイトデータに変換 (JPEG形式)
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='JPEG', quality=85, optimize=True)
                img_byte_arr = img_byte_arr.getvalue()
                
                # ファイル名を決定 (料理名_タイムスタンプ.jpg)
                timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                # 日本語ファイル名はトラブルの元なので、タイムスタンプをメインにする
                img_filename = f"img_{timestamp}.jpg"
                
                # GitHubに画像をアップロード
                repo.create_file(
                    path=f"docs/images/{img_filename}",
                    message=f"Add image for {title}",
                    content=img_byte_arr
                )
                image_path = f"../images/{img_filename}"
                st.success(f"画像 {img_filename} をアップロードしました！")

            # 3. Markdownテキストの作成
            md_content = f"# {title}\n\n"
            
            if image_path:
                md_content += f"![{title}]({image_path})\n\n"
            
            md_content += f"## 材料\n{ingredients}\n\n"
            md_content += f"## 手順\n{steps}\n\n"
            if memo:
                md_content += f"## メモ\n{memo}\n"

            # 4. Markdownファイルのアップロード
            # ファイル名を作成 (カテゴリ/料理名.md)
            # 既に同名ファイルがあるとエラーになるので注意
            file_path = f"docs/{CATEGORIES[category_key]}/{title}.md"
            
            repo.create_file(
                path=file_path,
                message=f"Add recipe: {title}",
                content=md_content
            )
            
            st.balloons()
            st.success(f"「{title}」のレシピを投稿しました！数分後にサイトに反映されます。")
            
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
