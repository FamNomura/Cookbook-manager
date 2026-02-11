import streamlit as st
from github import Github, UnknownObjectException
from PIL import Image
import io
import datetime
import re

# --- 設定 ---
st.set_page_config(page_title="レシピ管理", page_icon="🍳")

# --- セッション状態の初期化 ---
# フォームの内容
if 'form_title' not in st.session_state: st.session_state.form_title = ""
if 'form_ingredients' not in st.session_state: st.session_state.form_ingredients = ""
if 'form_steps' not in st.session_state: st.session_state.form_steps = ""
if 'form_memo' not in st.session_state: st.session_state.form_memo = ""
if 'current_image_path' not in st.session_state: st.session_state.current_image_path = ""

# ファイル管理用 (リネーム・削除判定に必須)
if 'original_file_path' not in st.session_state: st.session_state.original_file_path = ""
if 'original_sha' not in st.session_state: st.session_state.original_sha = ""

# --- 関数定義 ---

@st.cache_data(ttl=600)
def get_existing_categories():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return []
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
    except:
        return []

def get_files_in_category(category):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo_name = st.secrets["REPO_NAME"]
        g = Github(token)
        repo = g.get_repo(repo_name)
        path = f"docs/{category}"
        contents = repo.get_contents(path)
        files = [c.name for c in contents if c.name.endswith(".md")]
        return files
    except:
        return []

def parse_markdown_to_form(md_text):
    """Markdownを解析してフォーム用テキストに戻す"""
    title_match = re.search(r'^#\s+(.+)$', md_text, re.MULTILINE)
    title = title_match.group(1) if title_match else ""

    image_match = re.search(r'!\[.*?\]\((.*?)\)', md_text)
    image_path = image_match.group(1) if image_match else ""

    sections = re.split(r'^##\s+', md_text, flags=re.MULTILINE)
    ingredients = ""
    steps = ""
    memo = ""

    for section in sections:
        if section.startswith("材料"):
            lines = section.replace("材料\n", "").strip().split('\n')
            clean_lines = [line.strip().lstrip('* ').strip() for line in lines if line.strip()]
            ingredients = "\n".join(clean_lines)
        elif section.startswith("手順"):
            lines = section.replace("手順\n", "").strip().split('\n')
            clean_lines = [re.sub(r'^\d+\.\s*', '', line).strip() for line in lines if line.strip()]
            steps = "\n".join(clean_lines)
        elif section.startswith("メモ"):
            raw_memo = section.replace("メモ\n", "").strip()
            memo = raw_memo.replace("  \n", "\n")

    return title, image_path, ingredients, steps, memo

def format_list(text, is_ordered=False):
    if not text: return ""
    lines = text.strip().split('\n')
    formatted = []
    for i, line in enumerate(lines):
        line = line.strip()
        if line:
            prefix = f"{i+1}. " if is_ordered else "* "
            formatted.append(f"{prefix}{line}")
    return "\n".join(formatted)

# --- UI構築 ---
st.title("🍳 レシピ管理システム Ver.5.0")

# モード選択
mode = st.radio("操作モード", ["新規作成", "既存レシピを編集・削除"], horizontal=True)

existing_cats = get_existing_categories()
final_category = ""
loaded = False # 読み込み済みフラグ

# --- ① 対象選択エリア ---
st.subheader("① 対象の選択")

if mode == "新規作成":
    # 新規作成モード
    cat_mode = st.radio("カテゴリ", ["既存から選ぶ", "新規作成する"], horizontal=True, key="new_cat_mode")
    if cat_mode == "既存から選ぶ":
        if existing_cats:
            final_category = st.selectbox("カテゴリ一覧", existing_cats, key="new_cat_select")
        else:
            st.warning("カテゴリがありません。新規作成してください。")
    else:
        final_category = st.text_input("新しいカテゴリ名", placeholder="例：調味料/タレ")
    
    # 状態リセット（編集モードから切り替わった場合）
    if st.session_state.get('last_mode') != 'new':
        st.session_state.form_title = ""
        st.session_state.form_ingredients = ""
        st.session_state.form_steps = ""
        st.session_state.form_memo = ""
        st.session_state.current_image_path = ""
        st.session_state.original_file_path = "" # パスもクリア
        st.session_state.last_mode = 'new'

else:
    # 編集・削除モード
    if existing_cats:
        select_cat = st.selectbox("カテゴリを選択", existing_cats, key="edit_cat_select")
        final_category = select_cat # 初期値として設定
        
        files = get_files_in_category(select_cat)
        if files:
            target_filename = st.selectbox("レシピを選択", files)
            
            if st.button("レシピを読み込む"):
                try:
                    with st.spinner("GitHubから取得中..."):
                        token = st.secrets["GITHUB_TOKEN"]
                        repo_name = st.secrets["REPO_NAME"]
                        g = Github(token)
                        repo = g.get_repo(repo_name)
                        
                        file_path = f"docs/{select_cat}/{target_filename}"
                        file_content = repo.get_contents(file_path)
                        md_text = file_content.decoded_content.decode("utf-8")
                        
                        # パース実行
                        p_title, p_img, p_ing, p_steps, p_memo = parse_markdown_to_form(md_text)
                        
                        # セッションに保存（重要：ここで元のパスとSHAを保存）
                        st.session_state.form_title = p_title
                        st.session_state.current_image_path = p_img
                        st.session_state.form_ingredients = p_ing
                        st.session_state.form_steps = p_steps
                        st.session_state.form_memo = p_memo
                        st.session_state.original_file_path = file_path # 元の場所
                        st.session_state.original_sha = file_content.sha # 上書き・削除用鍵
                        st.session_state.last_mode = 'edit'
                        
                        st.success(f"読み込み完了：{file_path}")
                        loaded = True
                except Exception as e:
                    st.error(f"読み込み失敗: {e}")
        else:
            st.info("このカテゴリにはレシピがありません。")
    else:
        st.warning("カテゴリが見つかりません。")

# --- ② 入力フォーム ---
st.subheader("② レシピ内容")

with st.form("recipe_form"):
    title = st.text_input("料理名", value=st.session_state.form_title, placeholder="例：豚の角煮")
    
    # 編集モードの場合、カテゴリ変更も可能にする
    if mode == "既存レシピを編集・削除":
        st.markdown("**カテゴリの変更（移動）**")
        if existing_cats:
            # 現在のカテゴリを初期値にする
            current_cat_index = 0
            # パスからカテゴリを逆算（docs/主菜/肉料理/豚.md -> 主菜/肉料理）
            if st.session_state.original_file_path:
                path_parts = st.session_state.original_file_path.split('/')
                if len(path_parts) > 2:
                    current_cat_str = "/".join(path_parts[1:-1])
                    if current_cat_str in existing_cats:
                        current_cat_index = existing_cats.index(current_cat_str)
            
            final_category = st.selectbox("カテゴリ", existing_cats, index=current_cat_index, key="form_cat_select")
        else:
            st.warning("カテゴリなし")

    uploaded_file = st.file_uploader("料理の写真 (変更する場合のみ)", type=['jpg', 'jpeg', 'png'])
    if st.session_state.current_image_path and not uploaded_file:
        st.caption(f"現在の画像: {st.session_state.current_image_path}")

    st.markdown("材料 (改行区切り)")
    raw_ingredients = st.text_area("材料", value=st.session_state.form_ingredients, height=150)

    st.markdown("手順 (改行区切り)")
    raw_steps = st.text_area("手順", value=st.session_state.form_steps, height=150)

    st.markdown("メモ (サイト上で改行反映)")
    raw_memo = st.text_area("メモ", value=st.session_state.form_memo)

    # 保存ボタン
    submit_label = "更新して保存" if mode == "既存レシピを編集・削除" else "新規投稿"
    submitted = st.form_submit_button(submit_label, type="primary")

# --- 保存処理 ---
if submitted:
    if not title:
        st.error("エラー：料理名を入力してください")
    elif not final_category:
        st.error("エラー：カテゴリが決まっていません")
    else:
        try:
            with st.spinner("処理中..."):
                token = st.secrets["GITHUB_TOKEN"]
                repo_name = st.secrets["REPO_NAME"]
                g = Github(token)
                repo = g.get_repo(repo_name)

                # A. 画像処理
                image_path = st.session_state.current_image_path
                if uploaded_file:
                    image = Image.open(uploaded_file)
                    max_size = 1200
                    if max(image.size) > max_size: image.thumbnail((max_size, max_size))
                    img_byte_arr = io.BytesIO()
                    if image.mode in ("RGBA", "P"): image = image.convert("RGB")
                    image.save(img_byte_arr, format='JPEG', quality=80, optimize=True)
                    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                    img_filename = f"img_{timestamp}.jpg"
                    repo.create_file(path=f"docs/images/{img_filename}", message=f"Img for {title}", content=img_byte_arr.getvalue())
                    image_path = f"../images/{img_filename}"

                # B. コンテンツ生成
                formatted_ing = format_list(raw_ingredients)
                formatted_stp = format_list(raw_steps, is_ordered=True)
                formatted_mem = raw_memo.replace('\n', '  \n') if raw_memo else ""

                md_content = f"# {title}\n\n"
                if image_path: md_content += f"![{title}]({image_path})\n\n"
                md_content += f"## 材料\n{formatted_ing}\n\n## 手順\n{formatted_stp}\n\n"
                if formatted_mem: md_content += f"## メモ\n{formatted_mem}\n"

                # C. 保存ロジック (重要：リネーム検知)
                clean_cat = final_category.strip().strip("/")
                new_file_path = f"docs/{clean_cat}/{title}.md"
                
                original_path = st.session_state.original_file_path
                original_sha = st.session_state.original_sha

                if mode == "新規作成":
                    # 新規作成
                    try:
                        repo.create_file(path=new_file_path, message=f"Create: {title}", content=md_content)
                        st.success(f"新規作成しました！ ({clean_cat}/{title})")
                    except Exception as e:
                        st.error(f"作成エラー (同名ファイルがあるかも): {e}")

                else:
                    # 編集モード
                    if not original_path:
                        st.error("編集対象が読み込まれていません。")
                    elif new_file_path == original_path:
                        # 1. パス変更なし (内容更新のみ)
                        repo.update_file(path=new_file_path, message=f"Update: {title}", content=md_content, sha=original_sha)
                        st.success("内容を更新しました！")
                    else:
                        # 2. パス変更あり (リネーム or 移動) -> 新規作成して旧削除
                        # 新規作成
                        repo.create_file(path=new_file_path, message=f"Move/Rename: {title}", content=md_content)
                        # 旧ファイル削除
                        repo.delete_file(path=original_path, message=f"Delete old: {original_path}", sha=original_sha)
                        st.success(f"移動・リネームしました！\n旧: {original_path}\n新: {new_file_path}")

                st.cache_data.clear()
                st.balloons()

        except Exception as e:
            st.error(f"エラー: {e}")

# --- ③ 削除エリア (編集モードのみ) ---
if mode == "既存レシピを編集・削除" and st.session_state.original_file_path:
    st.markdown("---")
    st.subheader("🗑️ レシピの削除")
    st.warning("この操作は取り消せません。")
    
    with st.expander("削除メニューを開く"):
        st.write(f"対象ファイル: `{st.session_state.original_file_path}`")
        confirm_delete = st.checkbox("本当に削除しますか？")
        
        if st.button("削除を実行する", disabled=not confirm_delete):
            try:
                with st.spinner("削除中..."):
                    token = st.secrets["GITHUB_TOKEN"]
                    repo_name = st.secrets["REPO_NAME"]
                    g = Github(token)
                    repo = g.get_repo(repo_name)
                    
                    repo.delete_file(
                        path=st.session_state.original_file_path,
                        message=f"Delete recipe: {st.session_state.original_file_path}",
                        sha=st.session_state.original_sha
                    )
                    
                    st.success("削除しました。")
                    st.cache_data.clear()
                    # セッション情報をクリア
                    st.session_state.form_title = ""
                    st.session_state.original_file_path = ""
                    st.rerun() # 画面リロード
            except Exception as e:
                st.error(f"削除エラー: {e}")
