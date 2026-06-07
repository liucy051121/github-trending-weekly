"""静态站点生成器

读取 data/*.json，用 Jinja2 渲染首页和每期详情页，
输出到 dist/，供 GitHub Pages 部署。
"""

import json
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
DIST_DIR = ROOT / "dist"

env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


def render_page(template_name: str, output_path: Path, **kwargs):
    template = env.get_template(template_name)
    html = template.render(**kwargs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"  rendered: {output_path}")


def build():
    # 清空输出目录
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir()

    # 复制静态文件
    dist_static = DIST_DIR / "static"
    shutil.copytree(STATIC_DIR, dist_static)
    print(f"  copied: {STATIC_DIR} -> {dist_static}")

    # 加载所有周数据
    weeks = sorted(
        [p.stem for p in DATA_DIR.glob("*.json")],
        reverse=True,
    )

    week_data = {}
    week_summaries = []
    for wk in weeks:
        data = json.loads((DATA_DIR / f"{wk}.json").read_text(encoding="utf-8"))
        week_data[wk] = data
        if data["repos"]:
            top = data["repos"][0]
            week_summaries.append({
                "week": wk,
                "repo_count": len(data["repos"]),
                "top_name": f"{top['owner']}/{top['name']}",
                "top_stars": top["stars_period"],
            })

    # 渲染首页
    render_page("index.html", DIST_DIR / "index.html", week_summaries=week_summaries)

    # 渲染每期详情页
    week_dir = DIST_DIR / "week"
    week_dir.mkdir(exist_ok=True)
    for wk, data in week_data.items():
        render_page("week.html", week_dir / f"{wk}.html", data=data)

    # 让 /week/2026-W23 不需要 .html 后缀 (GitHub Pages 默认行为)
    # 重命名为文件夹形式: /week/2026-W23/index.html
    for wk in week_data:
        dir_path = week_dir / wk
        dir_path.mkdir(exist_ok=True)
        old_path = week_dir / f"{wk}.html"
        new_path = dir_path / "index.html"
        old_path.rename(new_path)

    print(f"\nDone: {len(week_data)} 期周报已生成到 {DIST_DIR}")


if __name__ == "__main__":
    build()
