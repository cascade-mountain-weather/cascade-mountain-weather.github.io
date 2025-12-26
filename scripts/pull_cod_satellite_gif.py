#!/usr/bin/env python3
import argparse
import os
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from selenium.webdriver.common.action_chains import ActionChains
def get_open_modal(driver: webdriver.Chrome) -> object:
	"""Return the visible modal/dialog container if present."""
	candidates = [
		"//div[contains(@class,'modal') and not(contains(@style,'display: none'))]",
		"//div[contains(@role,'dialog')]",
		"//div[contains(@class,'Dialog') and not(contains(@style,'display: none'))]",
	]
	for xp in candidates:
		try:
			el = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, xp)))
			return el
		except Exception:
			continue
	# fallback: any element with 'save' or 'download' visible
	try:
		el = WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, "//*[contains(., 'Save Animated GIF') or contains(., 'Save GIF')]/ancestor::*[contains(@class,'modal') or contains(@role,'dialog')][1]")))
		return el
	except Exception:
		return None


def setup_driver(download_dir: Path, headless: bool = False) -> webdriver.Chrome:
	opts = webdriver.ChromeOptions()
	prefs = {
		"download.default_directory": str(download_dir.resolve()),
		"download.prompt_for_download": False,
		"download.directory_upgrade": True,
		"safebrowsing.enabled": True,
		"profile.default_content_setting_values.automatic_downloads": 1,
	}
	opts.add_experimental_option("prefs", prefs)
	# Headless can be flaky for downloads; default to visible
	if headless:
		opts.add_argument("--headless=new")
	opts.add_argument("--start-maximized")
	driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
	return driver


def click_save_animation(driver: webdriver.Chrome, debug: bool = False, modal_timeout_s: float = 10.0):
	wait = WebDriverWait(driver, max(5, modal_timeout_s))

	def log(msg: str):
		if debug:
			print(f"[save] {msg}")

	# Shortcut-only approach: focus viewer/body, send 'S' via multiple methods, then wait for modal
	body = driver.find_element(By.TAG_NAME, 'body')

	# Try focusing known viewer container
	viewer = None
	for selector in [
		"//div[contains(@id,'data_viewer') or contains(@class,'data_viewer') or contains(@class,'viewer')]",
		"//canvas",
		"//div[contains(@class,'leaflet-container') or contains(@id,'map')]",
	]:
		try:
			viewer = driver.find_element(By.XPATH, selector)
			ActionChains(driver).move_to_element(viewer).click(viewer).perform()
			log(f"Focused viewer via {selector}")
			break
		except Exception:
			continue

	if viewer is None:
		ActionChains(driver).move_to_element(body).click(body).perform()
		log("Focused body")

	# Send a single shortcut attempt: prefer direct key to body; fallback to one JS dispatch
	sent = False
	try:
		body.send_keys('S')
		sent = True
		log("Sent 'S' to body (single attempt)")
	except Exception:
		pass
	if not sent:
		try:
			driver.execute_script("window.focus();")
			driver.execute_script("document.dispatchEvent(new KeyboardEvent('keydown', {key:'S',code:'KeyS',keyCode:83,which:83,bubbles:true}));")
			sent = True
			log("Dispatched JS keydown 'S' (single attempt)")
		except Exception:
			pass

	# Wait for modal presence indicating Save dialog opened
	try:
		wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'modal') or contains(@role,'dialog')]//button[contains(., 'Save Animated GIF') or contains(., 'Save GIF')"])))
		log("Save dialog detected")
		return
	except Exception:
				raise RuntimeError("Save dialog not detected after sending shortcut 'S'.")


def fill_animation_form(
	driver: webdriver.Chrome,
	width: int | None = None,
	height: int | None = None,
	delay_ms: int | None = None,
	loop: bool = True,
	speed_fps: int | None = None,
	loop_delay_ms: int | None = None,
	start_frame: int | str | None = None,
	end_frame: int | str | None = None,
	modal_el: object | None = None,
):
	wait = WebDriverWait(driver, 20)
	# Wait for a modal/dialog to show up that has inputs
	# Strategy: find numeric inputs and map in order: width, height, delay
	# If labels exist, prefer label pairing
    
	def adjust_number_input(input_el, target_value: float):
		"""Adjust a numeric input to target value using spinner arrows or arrow keys."""
		try:
			current_raw = input_el.get_attribute("value")
			current = float(current_raw) if current_raw not in (None, "") else None
		except Exception:
			current = None
		try:
			step_raw = input_el.get_attribute("step")
			step = float(step_raw) if step_raw not in (None, "", "any") else 1.0
		except Exception:
			step = 1.0
		# Focus the input
		try:
			driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth',block:'center'});", input_el)
			input_el.click()
		except Exception:
			pass
		# If we know current, compute clicks; else do a reasonable number of arrow ups
		try:
			import math
			if current is not None:
				delta = target_value - current
				clicks = int(round(abs(delta) / max(step, 1e-6)))
				key = Keys.ARROW_UP if delta > 0 else Keys.ARROW_DOWN
				for _ in range(clicks):
					input_el.send_keys(key)
					time.sleep(0.05)
				return True
			else:
				# Unknown current; attempt to set via JS, then nudge with a few arrow presses
				driver.execute_script("arguments[0].value=arguments[1]; arguments[0].dispatchEvent(new Event('input',{bubbles:true})); arguments[0].dispatchEvent(new Event('change',{bubbles:true}));", input_el, str(target_value))
				for _ in range(3):
					input_el.send_keys(Keys.ARROW_UP)
					time.sleep(0.05)
				return True
		except Exception:
			pass
		# Try clicking explicit spinner buttons near the input
		try:
			inc = None
			dec = None
			for xp in [
				".//following::button[contains(@aria-label,'Increase') or contains(@title,'Increase') or contains(., '+')][1]",
				"./ancestor::*[1]//button[contains(@aria-label,'Increase') or contains(@title,'Increase') or contains(., '+')][1]",
			]:
				try:
					inc = input_el.find_element(By.XPATH, xp)
					break
				except Exception:
					continue
			for xp in [
				".//following::button[contains(@aria-label,'Decrease') or contains(@title,'Decrease') or contains(., '-')][1]",
				"./ancestor::*[1]//button[contains(@aria-label,'Decrease') or contains(@title,'Decrease') or contains(., '-')][1]",
			]:
				try:
					dec = input_el.find_element(By.XPATH, xp)
					break
				except Exception:
					continue
			if inc is None and dec is None:
				return False
			# If we can read current and step, click accordingly
			if current is not None:
				delta = target_value - current
				clicks = int(round(abs(delta) / max(step, 1e-6)))
				button = inc if delta > 0 else dec
				for _ in range(clicks):
					try:
						button.click()
					except Exception:
						driver.execute_script("arguments[0].click();", button)
					time.sleep(0.05)
				return True
			else:
				# Click increase a few times as a best-effort
				if inc:
					for _ in range(5):
						try:
							inc.click()
						except Exception:
							driver.execute_script("arguments[0].click();", inc)
						time.sleep(0.05)
					return True
			return False
		except Exception:
			return False

	# 1) Try label-driven mapping
	scope_root = modal_el if modal_el is not None else driver

	def set_input_for_label(label_text: str, value: str):
		try:
			label = scope_root.find_element(By.XPATH, f".//label[contains(., '{label_text}')]")
			# the corresponding input is usually next in the DOM
			# prefer the closest input/select following the label
			input_el = None
			for xpath in [
				".//following::input[1]",
				".//following::select[1]",
			]:
				try:
					el = label.find_element(By.XPATH, xpath)
					input_el = el
					break
				except Exception:
					continue
			if input_el is None:
				return False
			tag = input_el.tag_name.lower()
			if tag == "input":
				# Prefer spinner adjustment for numeric inputs
				input_type = (input_el.get_attribute("type") or "").lower()
				if input_type == "number":
					try:
						return adjust_number_input(input_el, float(value))
					except Exception:
						pass
				# Fallback to direct entry
				input_el.clear()
				input_el.send_keys(value)
			elif tag == "select":
				# try to select option that matches value
				try:
					opt = input_el.find_element(By.XPATH, f".//option[contains(., '{value}')]")
					opt.click()
				except Exception:
					# fallback: set via keys
					input_el.send_keys(value)
			return True
		except Exception:
			return False

	# Set core sizing/delay if provided
	if width is not None:
		set_input_for_label("Width", str(width))
	if height is not None:
		set_input_for_label("Height", str(height))
	if delay_ms is not None:
		# Some dialogs label this as "Frame Delay"
		ok = set_input_for_label("Delay", str(delay_ms)) or set_input_for_label("Frame Delay", str(delay_ms))

	# Animation Speed (frames/sec)
	if speed_fps is not None:
		set_input_for_label("Animation Speed", str(speed_fps))

	# Loop Delay (milliseconds before restarting)
	if loop_delay_ms is not None:
		set_input_for_label("Loop Delay", str(loop_delay_ms))

	# Animation Start/End (frame indexes or time codes)
	if start_frame is not None:
		ok_start = set_input_for_label("Animation Start", str(start_frame)) or set_input_for_label("Start", str(start_frame)) or set_input_for_label("Start Time", str(start_frame))
	if end_frame is not None:
		ok_end = set_input_for_label("Animation End", str(end_frame)) or set_input_for_label("End", str(end_frame)) or set_input_for_label("End Time", str(end_frame))

	# Fallbacks: attempt to find inputs by name/placeholder attributes
	try:
		dialog_inputs = wait.until(EC.presence_of_all_elements_located((By.XPATH, ".//input | .//select"))) if modal_el else wait.until(EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class,'modal') or contains(@class,'Dialog') or contains(@role,'dialog')]//input | //div[contains(@class,'modal') or contains(@class,'Dialog') or contains(@role,'dialog')]//select")))
		for el in dialog_inputs:
			name = (el.get_attribute("name") or "").lower()
			placeholder = (el.get_attribute("placeholder") or "").lower()
			label_key = name or placeholder
			def set_val(val):
				try:
					if el.tag_name.lower() == "input":
						input_type = (el.get_attribute("type") or "").lower()
						if input_type == "number":
							return adjust_number_input(el, float(val))
						el.clear()
						el.send_keys(str(val))
					else:
						# select
						opt = el.find_element(By.XPATH, f".//option[contains(., '{val}')]")
						opt.click()
					return True
				except Exception:
					# fallback: set via JS + events
					try:
						driver.execute_script("arguments[0].value=arguments[1]; arguments[0].dispatchEvent(new Event('input',{bubbles:true})); arguments[0].dispatchEvent(new Event('change',{bubbles:true}));", el, str(val))
						return True
					except Exception:
						return False
			if speed_fps is not None and ("speed" in label_key or "animation speed" in label_key):
				set_val(speed_fps)
			if loop_delay_ms is not None and ("loop" in label_key and "delay" in label_key):
				set_val(loop_delay_ms)
			if start_frame is not None and ("start" in label_key or "start time" in label_key):
				set_val(start_frame)
			if end_frame is not None and ("end" in label_key or "end time" in label_key):
				set_val(end_frame)
			if width is not None and ("width" in label_key):
				set_val(width)
			if height is not None and ("height" in label_key):
				set_val(height)
			if delay_ms is not None and ("delay" in label_key and "frame" in label_key):
				set_val(delay_ms)
	except Exception:
		pass

	# Loop checkbox (GIF looping)
	try:
		loop_box = scope_root.find_element(By.XPATH, ".//label[contains(., 'Loop')]/following::input[@type='checkbox'][1]")
		if loop_box.is_selected() != loop:
			loop_box.click()
	except Exception:
		# ignore if not present
		pass


def click_save_gif(driver: webdriver.Chrome, modal_el: object | None = None, debug: bool = False):
	wait = WebDriverWait(driver, 30)
	container = modal_el if modal_el is not None else driver
	selectors = [
		".//button[contains(., 'Save Animated GIF') or contains(., 'Save GIF')]",
		".//*[self::a or self::div][contains(., 'Save Animated GIF') or contains(., 'Save GIF')]",
	]
	last_err = None
	for xp in selectors:
		try:
			el = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
			driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth',block:'center'});", el)
			try:
				el.click()
			except Exception:
				driver.execute_script("arguments[0].click();", el)
			return
		except Exception as e:
			last_err = e
			continue
	# As a last resort, click any element with id/class containing 'save' inside modal
	try:
		el = container.find_element(By.XPATH, ".//*[@id[contains(.,'save')] or contains(@class,'save')]")
		driver.execute_script("arguments[0].click();", el)
		return
	except Exception:
		pass
	raise RuntimeError(f"Could not click Save GIF: {last_err}")


def wait_for_download(download_dir: Path, timeout: int = 60) -> Path | None:
	"""Poll the download directory for a new .gif file."""
	start = time.time()
	# Record existing files first
	existing = set(p.name for p in download_dir.glob("*.gif"))
	while time.time() - start < timeout:
		for p in download_dir.glob("*.gif"):
			if p.name not in existing:
				# Chrome may write .crdownload while in-progress; ensure size stabilizes
				size1 = p.stat().st_size
				time.sleep(1.0)
				size2 = p.stat().st_size
				if size2 >= size1:
					return p
		time.sleep(1.0)
	return None


def main():
	parser = argparse.ArgumentParser(description="Download COD satellite GIF via automation")
	parser.add_argument("--url", default="https://weather.cod.edu/satrad/?parms=regional-w_northwest-truecolor-24-1-100-4&checked=map&colorbar=undefined", help="COD SatRad URL")
	parser.add_argument("--out", default=str((Path(__file__).parent.parent / "assets" / "images").resolve()), help="Download directory")
	parser.add_argument("--width", type=int, default=None, help="GIF width")
	parser.add_argument("--height", type=int, default=None, help="GIF height")
	parser.add_argument("--delay", type=int, default=None, help="Frame delay in ms")
	parser.add_argument("--speed", type=int, default=None, help="Animation speed (frames/sec)")
	parser.add_argument("--loop-delay", type=int, default=None, help="Loop delay (ms)")
	parser.add_argument("--start", type=int, default=None, help="Animation start frame index")
	parser.add_argument("--end", type=int, default=None, help="Animation end frame index")
	parser.add_argument("--loop", action="store_true", help="Enable GIF loop")
	parser.add_argument("--headless", action="store_true", help="Run Chrome headless")
	parser.add_argument("--last-hours", type=int, default=3, help="Limit animation to the last N hours (updates URL frame count)")
	parser.add_argument("--frame-interval", type=int, default=5, help="Minutes per frame for product; used to compute frames for last-hours")
	parser.add_argument("--frames", type=int, default=None, help="Explicit number of frames to request (overrides last-hours computation)")
	parser.add_argument("--filename", type=str, default="cod_goes_visible_3hr.gif", help="Final filename for the downloaded GIF")
	parser.add_argument("--debug", action="store_true", help="Enable verbose debug logs")
	parser.add_argument("--open-wait-ms", type=int, default=1500, help="Extra wait after save dialog opens before filling form (ms)")
	parser.add_argument("--use-default", action="store_true", help="Skip manual form entry and save the default animation length shown")
	parser.add_argument("--modal-timeout-ms", type=int, default=8000, help="Maximum time to wait for the save modal to appear (ms)")
	parser.add_argument("--save-button-timeout-ms", type=int, default=8000, help="Maximum time to wait for Save GIF button to become clickable (ms)")
	parser.add_argument("--download-timeout", type=int, default=180, help="Maximum seconds to wait for GIF download to complete")

	args = parser.parse_args()
	download_dir = Path(args.out)
	download_dir.mkdir(parents=True, exist_ok=True)

	# If last-hours is specified, adjust URL frames parameter accordingly
	url = args.url
	if args.last_hours is not None or args.frames is not None:
		try:
			if args.frames is not None:
				frames_needed = max(1, int(args.frames))
			else:
				frames_needed = max(1, round((args.last_hours * 60) / max(1, args.frame_interval)))
			# Parse URL and update the 'parms' token numeric part representing frames
			parsed = urlparse(url)
			qs = parse_qs(parsed.query)
			parms = None
			if "parms" in qs:
				parms = qs["parms"][0]
			else:
				# Sometimes 'parms' may be in path; handle basic case
				parms = None
			if parms:
				parts = parms.split("-")
				# Heuristic: first numeric part after the product token is frames
				# Find index of first purely numeric token starting at index 3
				idx = None
				for i in range(3, len(parts)):
					if parts[i].isdigit():
						idx = i
						break
				if idx is not None:
					parts[idx] = str(frames_needed)
					qs["parms"] = ["-".join(parts)]
					new_query = urlencode(qs, doseq=True)
					url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
					if args.debug:
						print(f"[frames] Using {frames_needed} frames (interval={args.frame_interval} min, last_hours={args.last_hours})")
		except Exception:
			# If parsing fails, continue with original URL
			pass

	driver = setup_driver(download_dir, headless=args.headless)
	try:
		driver.get(url)
		# Allow tiles and controls to load
		time.sleep(3)
		click_save_animation(driver, debug=args.debug, modal_timeout_s=args.modal_timeout_ms/1000.0)
		# Give the modal a moment to fully render
		if args.open_wait_ms and args.open_wait_ms > 0:
			time.sleep(args.open_wait_ms / 1000.0)
		# Ensure the Save GIF button is clickable before filling
		try:
			modal_container = get_open_modal(driver)
			WebDriverWait(driver, max(3, args.save_button_timeout_ms/1000.0)).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Save Animated GIF') or contains(., 'Save GIF')]")))
		except Exception:
			pass
		if args.use_default:
			# Use the viewer's default length; only set speed/loop settings
			fill_animation_form(
				driver,
				width=None,
				height=None,
				delay_ms=None,
				loop=args.loop,
				speed_fps=args.speed,
				loop_delay_ms=args.loop_delay,
				start_frame=None,
				end_frame=None,
				modal_el=modal_container,
			)
		else:
			fill_animation_form(
				driver,
				width=args.width,
				height=args.height,
				delay_ms=args.delay,
				loop=args.loop,
				speed_fps=args.speed,
				loop_delay_ms=args.loop_delay,
				start_frame=args.start,
				end_frame=args.end,
				modal_el=modal_container,
			)
		click_save_gif(driver, modal_el=modal_container, debug=args.debug)
		gif_path = wait_for_download(download_dir, timeout=args.download_timeout)
		if gif_path:
			# Rename to requested filename
			target_path = download_dir / args.filename
			try:
				if target_path.exists():
					target_path.unlink()
				gif_path.rename(target_path)
				print(f"✓ Saved GIF as: {target_path}")
			except Exception:
				print(f"✓ Downloaded GIF: {gif_path} (rename to {target_path.name} failed)")
		else:
			print("⚠ Timed out waiting for GIF download. Check selectors or site state.")
	finally:
		driver.quit()


if __name__ == "__main__":
	main()

