import shutil
from pathlib import Path

base_dir = Path(__file__).resolve().parent
screenshots_dir = base_dir / "app_screenshots"
media_dir = base_dir / "media"

media_dir.mkdir(exist_ok=True)

img_map = {
    "Screenshot 2026-08-01 160612.png": "image12.png",
    "Diagnose_report_Screenshot.png": "image13.png",
    "full_report_Screenshot.png": "image14.png"
}

for src_name, dst_name in img_map.items():
    src_file = screenshots_dir / src_name
    dst_file = media_dir / dst_name
    if src_file.exists():
        shutil.copy(src_file, dst_file)
        print(f"Copied {src_file.name} -> {dst_file.name}")
    else:
        print(f"Warning: {src_file.name} not found.")

print("Image copy complete!")
