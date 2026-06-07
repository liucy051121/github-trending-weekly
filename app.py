"""GitHub 每周星标榜单 - Flask 应用"""

import sys
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, abort, jsonify

from scraper import (
    fetch_trending,
    save_weekly,
    load_week,
    get_all_weeks,
    get_week_key,
)

app = Flask(__name__)


@app.route("/")
def index():
    weeks = get_all_weeks()
    week_summaries = []
    for wk in weeks:
        data = load_week(wk)
        if data and data["repos"]:
            top = data["repos"][0]
            week_summaries.append({
                "week": wk,
                "repo_count": len(data["repos"]),
                "top_name": f"{top['owner']}/{top['name']}",
                "top_stars": top["stars_period"],
            })
    return render_template("index.html", week_summaries=week_summaries)


@app.route("/week/<week_key>")
def week_detail(week_key):
    data = load_week(week_key)
    if not data:
        abort(404)
    return render_template("week.html", data=data)


@app.route("/week/<week_key>/")
def week_detail_slash(week_key):
    data = load_week(week_key)
    if not data:
        abort(404)
    return render_template("week.html", data=data)


@app.route("/scrape", methods=["POST"])
def scrape_now():
    """手动触发抓取"""
    try:
        repos = fetch_trending()
        if not repos:
            return jsonify({"ok": False, "error": "抓取结果为空，请检查网络或 GitHub 页面结构。"}), 500
        week_key = get_week_key()
        filepath = save_weekly(repos, week_key)
        return jsonify({
            "ok": True,
            "week": week_key,
            "count": len(repos),
            "message": f"已保存 {len(repos)} 个仓库到 {filepath}",
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _next_monday_8am() -> float:
    """计算到下一个周一 8:00 的秒数"""
    now = datetime.now()
    days_until_monday = (7 - now.weekday()) % 7
    if days_until_monday == 0 and now.hour >= 8:
        days_until_monday = 7
    target = now.replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=days_until_monday)
    return max(0, (target - now).total_seconds())


def _schedule_weekly():
    """后台线程：每周一 8:00 自动抓取"""
    delay = _next_monday_8am()
    next_time = datetime.now() + timedelta(seconds=delay)
    print(f"[定时] 下次抓取: {next_time.strftime('%Y-%m-%d %H:%M:%S')} ({(delay / 3600):.1f} 小时后)")

    def _scrape_and_reschedule():
        print(f"[定时] 开始抓取...")
        try:
            repos = fetch_trending()
            if repos:
                week_key = get_week_key()
                save_weekly(repos, week_key)
                print(f"[定时] 已保存: {week_key} ({len(repos)} 个仓库)")
            else:
                print("[定时] 抓取结果为空，将跳过本周 (可稍后手动抓取补救)")
        except Exception as e:
            print(f"[定时] 抓取失败: {e}，将跳过本周 (可稍后手动抓取补救)")
        # 排下一个周一
        next_delay = _next_monday_8am()
        threading.Timer(next_delay, _scrape_and_reschedule).start()

    threading.Timer(delay, _scrape_and_reschedule).start()


def do_scrape():
    """CLI 模式下的手动抓取"""
    print("正在抓取 GitHub Trending ...")
    repos = fetch_trending()
    if not repos:
        print("没有抓到数据，请检查网络或 GitHub 页面结构是否变化。")
        sys.exit(1)
    week_key = get_week_key()
    filepath = save_weekly(repos, week_key)
    print(f"已保存 {len(repos)} 个仓库到 {filepath}")
    for r in repos:
        print(f"  #{r['rank']} {r['owner']}/{r['name']}  +{r['stars_period']}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "scrape":
        do_scrape()
    else:
        _schedule_weekly()
        print("启动开发服务器: http://127.0.0.1:5000")
        app.run(debug=True, host="127.0.0.1", port=5000)
