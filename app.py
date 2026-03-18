import time
import platform
import pandas as pd
import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ── 設定 ──────────────────────────────────────────────
SEARCH_QUERY = "肉蛋吐司 紅茶牛奶 台中"
MAX_STAR     = 2
SCROLL_PAUSE = 2
# ──────────────────────────────────────────────────────


def init_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=zh-TW")
    options.add_argument("--window-size=1920,1080")

    # Streamlit Cloud（Linux）使用系統 Chromium
    if platform.system() == "Linux":
        options.binary_location = "/usr/bin/chromium-browser"
        driver = webdriver.Chrome(
            options=options
        )
    else:
        # 本機 Windows/Mac 使用 webdriver-manager
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
    return driver


def search_place(driver, query):
    driver.get("https://www.google.com/maps")
    wait = WebDriverWait(driver, 15)
    search_box = wait.until(EC.presence_of_element_located((By.ID, "searchboxinput")))
    search_box.clear()
    search_box.send_keys(query)
    search_box.send_keys(Keys.ENTER)
    time.sleep(4)


def open_reviews(driver):
    wait = WebDriverWait(driver, 15)
    tabs = wait.until(EC.presence_of_all_elements_located(
        (By.CSS_SELECTOR, "button[role='tab']")
    ))
    for tab in tabs:
        if "評論" in tab.text or "Reviews" in tab.text:
            tab.click()
            break
    time.sleep(3)


def sort_by_lowest(driver):
    wait = WebDriverWait(driver, 15)
    sort_btn = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "button[data-value='排序'],"
                          "button[aria-label*='排序'],"
                          "button[aria-label*='Sort']")
    ))
    sort_btn.click()
    time.sleep(1)

    menu_items = driver.find_elements(By.CSS_SELECTOR, "li[role='menuitemradio']")
    for item in menu_items:
        if "最低" in item.text or "Lowest" in item.text:
            item.click()
            break
    time.sleep(3)


def scroll_reviews(driver, status):
    scrollable = driver.find_element(
        By.CSS_SELECTOR, "div[role='feed'], div.m6QErb.DxyBCb"
    )
    last_height = 0
    count = 0
    while True:
        driver.execute_script(
            "arguments[0].scrollTop = arguments[0].scrollHeight", scrollable
        )
        time.sleep(SCROLL_PAUSE)
        new_height = driver.execute_script(
            "return arguments[0].scrollHeight", scrollable
        )
        count += 1
        status.text(f"載入中... 已滾動 {count} 次")
        if new_height == last_height:
            break
        last_height = new_height


def expand_all_reviews(driver):
    while True:
        more_btns = driver.find_elements(
            By.CSS_SELECTOR,
            "button.w8nwRe, button[aria-label*='更多'], button[aria-label*='More']"
        )
        if not more_btns:
            break
        for btn in more_btns:
            try:
                driver.execute_script("arguments[0].click();", btn)
            except Exception:
                pass
        time.sleep(1)


def parse_reviews(driver):
    reviews = []
    cards = driver.find_elements(By.CSS_SELECTOR, "div.jftiEf, div[data-review-id]")

    for card in cards:
        try:
            stars_el = card.find_elements(
                By.CSS_SELECTOR, "span[aria-label*='顆星'], span[aria-label*='star']"
            )
            if not stars_el:
                continue
            aria = stars_el[0].get_attribute("aria-label")
            star_count = int(''.join(filter(str.isdigit, aria.split()[0])))

            if star_count > MAX_STAR:
                continue

            author_el = card.find_elements(By.CSS_SELECTOR, "div.d4r55, .WNxzHc button")
            author = author_el[0].text.strip() if author_el else "匿名"

            date_el = card.find_elements(By.CSS_SELECTOR, "span.rsqaWe")
            date = date_el[0].text.strip() if date_el else ""

            text_el = card.find_elements(By.CSS_SELECTOR, "span.wiI7pd, div.MyEned span")
            text = text_el[0].text.strip() if text_el else ""

            reviews.append({
                "星數": star_count,
                "作者": author,
                "日期": date,
                "評論內容": text
            })
        except Exception:
            continue

    return reviews


# ── Streamlit UI ───────────────────────────────────────
st.set_page_config(page_title="Google Maps 負評爬蟲", page_icon="⭐", layout="wide")
st.title("⭐ 肉蛋吐司 紅茶牛奶｜Google Maps 負評查詢")
st.caption(f"自動抓取 {MAX_STAR} 星以下的評論")

if st.button("開始抓取負評", type="primary"):
    driver = None
    try:
        with st.status("執行中...", expanded=True) as status:
            status.text("啟動瀏覽器...")
            driver = init_driver()

            status.text("開啟 Google Maps...")
            search_place(driver, SEARCH_QUERY)

            status.text("切換至評論頁籤...")
            open_reviews(driver)

            status.text("依最低評分排序...")
            sort_by_lowest(driver)

            scroll_reviews(driver, status)

            status.text("展開所有評論...")
            expand_all_reviews(driver)

            status.text("解析評論資料...")
            reviews = parse_reviews(driver)
            status.update(label="完成！", state="complete")

        if reviews:
            df = pd.DataFrame(reviews)
            st.success(f"共找到 {len(df)} 則負評")
            st.dataframe(df, use_container_width=True)

            csv = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                label="下載 CSV",
                data=csv,
                file_name="negative_reviews.csv",
                mime="text/csv"
            )
        else:
            st.warning("未找到符合條件的負評。")

    except Exception as e:
        st.error(f"發生錯誤：{e}")
    finally:
        if driver:
            driver.quit()
