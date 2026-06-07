"""GitHub Trending 爬虫模块

抓取 https://github.com/trending?since=weekly 页面前十仓库数据。
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"

WEEKLY_TRENDING_URL = "https://github.com/trending?since=weekly"
TIMEOUT = 15

# ── LLM 翻译配置 ──────────────────────────────────────────
# 优先使用环境变量中的 API 配置，否则 fallback 到本站的内置 key
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_API_BASE = os.environ.get("LLM_API_BASE", "https://api.openai.com/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

# ── 翻译缓存 ──────────────────────────────────────────────
CACHE_FILE = ROOT / "translation_cache.json"
_translation_cache: dict[str, str] = {}


def _load_cache():
    global _translation_cache
    if CACHE_FILE.exists():
        try:
            _translation_cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            _translation_cache = {}


def _save_cache():
    CACHE_FILE.write_text(
        json.dumps(_translation_cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


_load_cache()


def translate_to_chinese(english_text: str) -> str:
    """用 LLM 将英文描述翻译为简洁的中文项目简介。

    结果会缓存到本地文件，避免重复调用 API。
    """
    text = english_text.strip()
    if not text:
        return ""

    # 缓存命中
    if text in _translation_cache:
        return _translation_cache[text]

    try:
        resp = requests.post(
            f"{LLM_API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {LLM_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个 GitHub 开源项目介绍翻译专家。请将用户的英文项目描述翻译为简洁、通顺的中文简介（50 字以内），只输出翻译结果，不要任何额外解释或格式。",
                    },
                    {"role": "user", "content": text},
                ],
                "temperature": 0.3,
                "max_tokens": 200,
            },
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"[翻译警告] LLM 翻译失败 ({text[:40]}...): {e}")
        # fallback 到英文原文
        result = text

    # 写入缓存
    _translation_cache[text] = result
    _save_cache()
    return result


# ── 旧的硬编码翻译表（保留作为缓存预热，防止上线后首次调用 API） ──
CN_SUMMARIES = {
    "chopratejas/headroom": "一个 LLM 输入压缩工具，能在保持回答质量的前提下，将工具输出、日志、文件、RAG 检索结果等内容压缩 60-95% 的 token 用量，大幅降低 API 调用成本。提供库、代理和 MCP 服务三种使用方式。",
    "microsoft/markitdown": "微软出品的文件转 Markdown 工具，支持将 Word、Excel、PowerPoint、PDF、图片、音频等多种格式一键转换为干净规范的 Markdown 文本，方便后续喂给 LLM 或其他文本处理流程。",
    "harry0703/MoneyPrinterTurbo": "利用 AI 大模型一键生成高清短视频的全自动化工具。只需提供文案主题，就能自动完成视频脚本、配音、字幕、画面素材的生成和合成，无需任何视频剪辑经验。",
    "revfactory/harness": "一个元技能框架，用于设计特定领域的 AI Agent 团队。你可以用它定义专业化 Agent 角色，并为每个 Agent 自动生成所需的技能配置，加速复杂任务的 Agent 协作开发。",
    "supermemoryai/supermemory": "面向 AI 时代的高性能记忆引擎和 API。提供极速、可扩展的长期记忆能力，让 AI 应用能够记住用户偏好和历史交互，适用于聊天机器人、个人助手等需要持久化上下文的场景。",
    "affaan-m/ECC": "一个 Agent 性能优化系统，为 Claude Code、Codex、Cursor 等主流 AI 编程助手提供技能增强、上下文记忆、安全策略和研发优先的开发方法论，全面提升编码 Agent 的能力上限。",
    "EveryInc/compound-engineering-plugin": "Compound Engineering 官方插件，为 Claude Code、Codex、Cursor 等 AI 编程助手提供结构化的工程化能力增强，帮助 Agent 在复杂项目中保持代码质量和架构一致性。",
    "Open-LLM-VTuber/Open-LLM-VTuber": "开源的 LLM 虚拟主播工具，支持免提语音交互、实时语音打断和 Live2D 动态形象渲染，可跨平台本地运行。让任何一个大语言模型都能「活」起来，拥有生动的虚拟形象。",
    "can1357/oh-my-pi": "终端 AI 编程助手，支持基于哈希锚点的精准代码编辑、优化的工具调用链、LSP 语言服务集成、Python 运行时、浏览器控制和子 Agent 调度，功能覆盖全面。",
    "Leonxlnx/taste-skill": "给 AI 编程助手加上「好品味」——防止 AI 生成无聊、千篇一律、缺乏设计感的代码。通过技能配置引导 AI 输出更优雅、更符合人类审美的方案，拒绝「AI 流水线味道」。",
}


def get_week_key() -> str:
    """返回当前 ISO 周编号，例如 '2026-W23'"""
    now = datetime.now()
    iso = now.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _parse_number(text: str) -> int:
    """将 '1,234' 或 '1.2k' 之类的文本转为整数"""
    text = text.strip().lower().replace(",", "")
    if text.endswith("k"):
        return int(float(text[:-1]) * 1000)
    return int(text) if text else 0


def fetch_trending() -> list[dict]:
    """抓取 GitHub Trending 每周前十仓库，返回有序列表。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    resp = requests.get(WEEKLY_TRENDING_URL, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    articles = soup.find_all("article", class_="Box-row")
    repos = []

    for article in articles[:10]:
        h2 = article.find("h2", class_="h3")
        if not h2:
            continue
        a_tag = h2.find("a")
        if not a_tag:
            continue
        href = a_tag.get("href", "").strip()
        parts = href.strip("/").split("/")
        if len(parts) < 2:
            continue
        owner = parts[0]
        repo_name = parts[1]
        url = f"https://github.com{href}"

        # 描述
        desc_p = article.find("p", class_="col-9")
        description = desc_p.get_text(strip=True) if desc_p else ""

        # 语言
        lang_span = article.find("span", itemprop="programmingLanguage")
        language = lang_span.get_text(strip=True) if lang_span else ""

        # 总星标
        stars_total = 0
        muted_links = article.find_all("a", class_="Link--muted")
        for link in muted_links:
            text = link.get_text(strip=True)
            if re.match(r"^[\d,.kK]+$", text):
                stars_total = _parse_number(text)
                break

        # 本周新增星标
        stars_period = 0
        period_span = article.find("span", class_="float-sm-right")
        if period_span:
            period_text = period_span.get_text(strip=True)
            match = re.search(r"[\d,.]+", period_text)
            num_str = match.group() if match else "0"
            stars_period = _parse_number(num_str)

        # 头像
        avatar = ""
        imgs = article.find_all("img", class_="avatar")
        if imgs:
            avatar = imgs[0].get("src", "")

        # 中文简介：优先查硬编码表（旧项目），否则调用 LLM 翻译
        cn_key = f"{owner}/{repo_name}"
        if cn_key in CN_SUMMARIES:
            summary_cn = CN_SUMMARIES[cn_key]
        else:
            summary_cn = translate_to_chinese(description)

        repos.append({
            "rank": len(repos) + 1,
            "owner": owner,
            "name": repo_name,
            "url": url,
            "description": description,
            "language": language,
            "stars": stars_total,
            "stars_period": stars_period,
            "avatar": avatar,
            "summary_cn": summary_cn,
        })

    return repos


def save_weekly(repos: list[dict], week_key: str) -> Path:
    """保存一周数据到 JSON 文件，返回文件路径。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    filepath = DATA_DIR / f"{week_key}.json"
    payload = {
        "week": week_key,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "repos": repos,
    }
    filepath.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return filepath


def load_week(week_key: str) -> Optional[dict]:
    """加载指定周的数据，不存在则返回 None。"""
    filepath = DATA_DIR / f"{week_key}.json"
    if not filepath.exists():
        return None
    return json.loads(filepath.read_text(encoding="utf-8"))


def get_all_weeks() -> list[str]:
    """返回所有已有的周编号，从新到旧排序。"""
    if not DATA_DIR.exists():
        return []
    return sorted(
        [p.stem for p in DATA_DIR.glob("*.json")],
        reverse=True,
    )

