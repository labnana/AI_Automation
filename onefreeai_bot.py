import os
import re
import time
import requests
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.chrome import ChromeDriverManager

# =========================
# SETTINGS
# =========================
WAIT_PAGE = 25
WAIT_IMAGE_GEN = 180
DOWNLOAD_DIR = str(Path.cwd() / "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# =========================
# LOAD PROMPTS
# =========================
with open("prompts.txt", "r", encoding="utf-8") as f:
    prompts = [p.strip() for p in f.read().split("\n\n") if p.strip()]

# Ratio logic
RATIO = "9:16" if len(prompts) <= 12 else "16:9"

print("Using ratio:", RATIO)
print("Download folder:", DOWNLOAD_DIR)

# =========================
# CHROME OPTIONS
# =========================
options = webdriver.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, WAIT_PAGE)
driver.get("https://draw.onefreeai.com/")

# =========================
# HELPERS
# =========================
def sanitize_filename(text, max_len=60):
    text = re.sub(r'[<>:"/\\|?*]+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_len]

def clear_prompt_box(box):
    box.click()
    time.sleep(0.3)
    box.send_keys(Keys.CONTROL, "a")
    time.sleep(0.2)
    box.send_keys(Keys.BACKSPACE)
    time.sleep(0.5)

def type_prompt(box, prompt):
    box.send_keys(prompt)

def get_http_imgs(min_w=120, min_h=120):
    imgs = driver.find_elements(By.TAG_NAME, "img")
    valid = []
    for img in imgs:
        try:
            src = img.get_attribute("src") or ""
            size = img.size
            if src.startswith("http") and size["width"] >= min_w and size["height"] >= min_h:
                valid.append(img)
        except:
            pass
    return valid

def get_generated_thumb_srcs():
    srcs = []
    for img in get_http_imgs():
        try:
            src = img.get_attribute("src") or ""
            if src and src not in srcs:
                srcs.append(src)
        except:
            pass
    return srcs

def open_size_dropdown():
    print("Trying to open size dropdown...")
    try:
        # Directly click the visible dropdown button near "Size"
        candidates = driver.find_elements(By.XPATH, "//*[contains(text(),'Size') or contains(text(),'size')]")
        for c in candidates:
            try:
                btns = c.find_elements(By.XPATH, "./following::button")
                for b in btns[:3]:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", b)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", b)
                    print("Size dropdown opened")
                    time.sleep(1.2)
                    return True
            except:
                pass
    except:
        pass

    try:
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for b in buttons:
            try:
                txt = (b.text or "").strip()
                if "1:1" in txt or "9:16" in txt or "16:9" in txt:
                    driver.execute_script("arguments[0].click();", b)
                    print("Size button clicked directly")
                    time.sleep(1.2)
                    return True
            except:
                pass
    except:
        pass

    print("Size dropdown NOT opened")
    return False

def select_ratio(ratio_text):
    print(f"Trying to select ratio: {ratio_text}")
    try:
        opts = driver.find_elements(By.XPATH, f"//*[normalize-space(text())='{ratio_text}']")
        for opt in opts:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", opt)
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", opt)
                print(f"Ratio selected: {ratio_text}")
                time.sleep(1)
                return True
            except:
                pass
    except:
        pass

    print("Ratio NOT selected")
    return False

def click_generate():
    print("Trying to click Generate...")
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for btn in buttons:
        try:
            txt = (btn.text or "").strip().lower()
            if "generate" in txt:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", btn)
                print("Generate clicked")
                return True
        except:
            pass
    print("Generate NOT found")
    return False

def wait_for_new_thumb_src(before_srcs, timeout=WAIT_IMAGE_GEN):
    start = time.time()
    while time.time() - start < timeout:
        current = get_generated_thumb_srcs()
        new = [s for s in current if s not in before_srcs]
        if new:
            print("New thumbnail src detected")
            return new[-1]
        time.sleep(2)
    return None

def click_new_thumb_by_src(target_src):
    print("Trying to click generated image thumbnail...")
    imgs = driver.find_elements(By.TAG_NAME, "img")
    for img in imgs:
        try:
            src = img.get_attribute("src") or ""
            if src == target_src:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", img)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", img)
                print("Generated image clicked")
                time.sleep(2.5)
                return True
        except:
            pass
    print("Generated image click failed")
    return False

def save_url_to_file(url, filename):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=60)
        if r.status_code == 200 and len(r.content) > 1000:
            path = os.path.join(DOWNLOAD_DIR, filename)
            with open(path, "wb") as f:
                f.write(r.content)
            print("Image saved:", path)
            return True
        else:
            print("Save failed. Status:", r.status_code, "Bytes:", len(r.content))
            return False
    except Exception as e:
        print("Save error:", e)
        return False

def is_preview_open():
    try:
        modal = driver.find_element(By.ID, "gen-image-modal-img")
        return modal.is_displayed()
    except:
        return False

def force_close_modal():
    """
    STRONG FIX:
    This closes the preview popup / half-window automatically.
    """
    print("Trying to close preview modal...")

    # If preview is not open, no need
    if not is_preview_open():
        print("Preview already closed")
        return True

    # -------------------------
    # METHOD 1: ESC
    # -------------------------
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.ESCAPE)
        time.sleep(2)
        if not is_preview_open():
            print("Preview closed by ESC")
            return True
    except Exception as e:
        print("ESC failed:", e)

    # -------------------------
    # METHOD 2: Click backdrop / outside image
    # -------------------------
    try:
        driver.execute_script("""
            let modalImg = document.getElementById('gen-image-modal-img');
            if (modalImg) {
                let overlay = modalImg.closest('div[role="dialog"]') || modalImg.parentElement.parentElement.parentElement;
                if (overlay) overlay.click();
            }
        """)
        time.sleep(2)
        if not is_preview_open():
            print("Preview closed by overlay click")
            return True
    except Exception as e:
        print("Overlay click failed:", e)

    # -------------------------
    # METHOD 3: Find red / top-right close button
    # -------------------------
    try:
        close_candidates = driver.find_elements(By.XPATH, "//button")
        for btn in close_candidates:
            try:
                txt = (btn.text or "").strip()
                aria = (btn.get_attribute("aria-label") or "").strip().lower()
                cls = (btn.get_attribute("class") or "").lower()

                if txt in ["×", "X", "x"] or "close" in aria or "close" in cls:
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(2)
                    if not is_preview_open():
                        print("Preview closed by close button")
                        return True
            except:
                pass
    except Exception as e:
        print("Close button search failed:", e)

    # -------------------------
    # METHOD 4: JS remove modal directly
    # -------------------------
    try:
        driver.execute_script("""
            let img = document.getElementById('gen-image-modal-img');
            if (img) {
                let parent = img.closest('div.fixed') || img.closest('div');
                if (parent) {
                    let p = parent;
                    for (let i = 0; i < 5; i++) {
                        if (p && p.parentElement) p = p.parentElement;
                    }
                    if (p) p.remove();
                } else {
                    img.remove();
                }
            }
        """)
        time.sleep(2)
        if not is_preview_open():
            print("Preview removed by JS")
            return True
    except Exception as e:
        print("JS remove failed:", e)

    print("Could NOT close preview modal")
    return False

# =========================
# PAGE READY
# =========================
wait.until(EC.presence_of_element_located((By.ID, "prompt")))
time.sleep(3)

# =========================
# MAIN LOOP
# =========================
for i, prompt in enumerate(prompts, start=1):
    print("\n" + "="*70)
    print(f"{i}: STARTING PROMPT")
    print(prompt[:120] + ("..." if len(prompt) > 120 else ""))

    try:
        # Close old preview if still open
        force_close_modal()

        # Snapshot before generate
        before_srcs = get_generated_thumb_srcs()
        print("Existing visible image src count:", len(before_srcs))

        # Prompt box
        box = wait.until(EC.element_to_be_clickable((By.ID, "prompt")))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", box)
        time.sleep(0.5)

        clear_prompt_box(box)
        type_prompt(box, prompt)
        time.sleep(1)

        # Open size dropdown
        if not open_size_dropdown():
            print("Skipping: size dropdown failed")
            continue

        # Select ratio
        if not select_ratio(RATIO):
            print("Skipping: ratio select failed")
            continue

        # Generate
        if not click_generate():
            print("Skipping: generate failed")
            continue

        # Wait for new generated image
        print("Waiting for new generated image...")
        new_src = wait_for_new_thumb_src(before_srcs, timeout=WAIT_IMAGE_GEN)
        if not new_src:
            print("No new image src detected -> skipping")
            continue

        print("New image URL:", new_src)

        # Click image so preview opens
        click_new_thumb_by_src(new_src)

        # Save file directly from URL
        filename = f"{i:03d}_{sanitize_filename(prompt)}.png"
        saved = save_url_to_file(new_src, filename)

        # Fallback: if modal image exists, save bigger src
        if not saved:
            try:
                big = driver.find_element(By.ID, "gen-image-modal-img")
                big_src = big.get_attribute("src")
                if big_src and big_src.startswith("http"):
                    print("Trying fallback modal src:", big_src)
                    saved = save_url_to_file(big_src, filename)
            except:
                pass

        if not saved:
            print("Final save failed for this prompt")
            force_close_modal()
            continue

        # =========================
        # CLOSE PREVIEW AUTOMATICALLY
        # =========================
        time.sleep(2)

        if is_preview_open():
            print("Preview is open -> closing now...")
            closed = force_close_modal()
            time.sleep(2)

            if not closed:
                print("WARNING: modal may still be open")
                # Last rescue: refresh page if modal still blocks next prompt
                try:
                    driver.refresh()
                    wait.until(EC.presence_of_element_located((By.ID, "prompt")))
                    time.sleep(4)
                    print("Page refreshed as rescue fix")
                except:
                    pass

        print("Prompt finished successfully. Moving to next...")
        time.sleep(3)

    except Exception as e:
        print("ERROR:", e)
        try:
            force_close_modal()
        except:
            pass
        continue

print("\nDONE")