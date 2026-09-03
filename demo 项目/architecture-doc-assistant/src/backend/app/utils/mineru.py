"""
MinerU 云服务客户端
===================
通过 https://mineru.net 官方云 API 解析 PDF/图片/Word/PPT。

工作流:
  1. POST /file-urls/batch → 获取签名上传 URL
  2. PUT 文件到上传 URL（不设 Content-Type）
  3. 轮询 GET /extract-results/batch/{batch_id} → done
  4. 下载 zip → 提取 Markdown

Token 从环境变量 MINERU_API_TOKEN 读取。
免费额度: 1000 页/天（最高优先级）。
"""

import io
import logging
import os
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://mineru.net/api/v4"
POLL_INTERVAL = 3       # 轮询间隔 (秒)
POLL_TIMEOUT = 300      # 最长等待 (秒)

_client_singleton: Optional["MinerUClient"] = None


def get_client() -> Optional["MinerUClient"]:
    """获取 MinerU 云客户端单例"""
    global _client_singleton
    if _client_singleton is None:
        token = os.getenv("MINERU_API_TOKEN", "")
        if token:
            logger.info(
                "[MinerU Client] 初始化云客户端 "
                "token_prefix=%s... token_len=%d",
                token[:8], len(token)
            )
            _client_singleton = MinerUClient(token)
        else:
            logger.info("[MinerU Client] MINERU_API_TOKEN 未设置，云解析不可用")
    return _client_singleton


def _ts() -> str:
    """返回当前时间戳字符串，用于日志"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def _elapsed(t0: float) -> str:
    """返回从 t0 到现在的耗时字符串"""
    return f"{time.time() - t0:.2f}s"


def _sz(n: int) -> str:
    """人性化文件大小"""
    if n < 1024:
        return f"{n}B"
    elif n < 1024**2:
        return f"{n/1024:.1f}KB"
    else:
        return f"{n/1024**2:.1f}MB"


class MinerUClient:
    """MinerU 云服务 HTTP 客户端"""

    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

    # ═══════════════════════════════════════════════════════
    #  公开接口
    # ═══════════════════════════════════════════════════════

    def parse_file(self, file_bytes: bytes, filename: str,
                   enable_formula: bool = True,
                   enable_table: bool = True,
                   is_ocr: bool = False,
                   language: str = "ch",
                   model: str = "vlm") -> Optional[str]:
        """
        上传本地文件到 MinerU 云服务并等待解析完成。

        Args:
            file_bytes: 文件二进制内容
            filename: 原始文件名
            enable_formula: 公式识别
            enable_table: 表格识别
            is_ocr: OCR 扫描版
            language: OCR 语言
            model: 模型版本 (pipeline / vlm / MinerU-HTML)

        Returns:
            解析后的 Markdown 文本，失败返回 None
        """
        t_total = time.time()

        logger.info(
            "[MinerU] ═══ 开始云解析: %s ═══",
            filename
        )
        logger.info(
            "[MinerU]     参数: size=%s  model=%s  ocr=%s  formula=%s  table=%s  lang=%s",
            _sz(len(file_bytes)), model, is_ocr, enable_formula, enable_table, language,
        )

        # ── Step 1: 获取上传 URL ──
        step1_t0 = time.time()
        logger.info("[MinerU] >>> Step 1/4: 请求签名上传 URL ...")
        batch_id = self._step1_request_upload_url(filename, model, is_ocr, enable_formula, enable_table, language)
        if not batch_id:
            logger.error("[MinerU] <<< Step 1/4: 失败! 无法获取上传 URL (总耗时=%s)", _elapsed(t_total))
            return None
        logger.info(
            "[MinerU] <<< Step 1/4: 完成  batch_id=%s  耗时=%s",
            batch_id, _elapsed(step1_t0),
        )

        # ── Step 2: PUT 上传文件 ──
        step2_t0 = time.time()
        logger.info("[MinerU] >>> Step 2/4: 上传文件到签名 URL (%s) ...", _sz(len(file_bytes)))
        if not self._step2_upload_file(file_bytes, filename):
            logger.error("[MinerU] <<< Step 2/4: 上传失败! (总耗时=%s)", _elapsed(t_total))
            return None
        logger.info("[MinerU] <<< Step 2/4: 上传完成  耗时=%s", _elapsed(step2_t0))

        # ── Step 3: 轮询解析结果 ──
        step3_t0 = time.time()
        logger.info(
            "[MinerU] >>> Step 3/4: 开始轮询解析结果 (间隔=%ds, 超时=%ds)",
            POLL_INTERVAL, POLL_TIMEOUT,
        )
        zip_bytes = self._step3_poll_result(batch_id)
        if not zip_bytes:
            logger.error("[MinerU] <<< Step 3/4: 轮询失败! (总耗时=%s)", _elapsed(t_total))
            return None
        logger.info(
            "[MinerU] <<< Step 3/4: 解析+下载完成  zip=%s  耗时=%s",
            _sz(len(zip_bytes)), _elapsed(step3_t0),
        )

        # ── Step 4: 提取 Markdown ──
        step4_t0 = time.time()
        logger.info("[MinerU] >>> Step 4/4: 从 zip 提取 Markdown ...")
        markdown = self._step4_extract_markdown(zip_bytes)
        if not markdown:
            logger.error("[MinerU] <<< Step 4/4: 提取失败! (总耗时=%s)", _elapsed(t_total))
            return None
        logger.info(
            "[MinerU] <<< Step 4/4: 提取完成  md_chars=%d  zip_files=%d  耗时=%s",
            len(markdown), self._last_zip_count, _elapsed(step4_t0),
        )

        total_elapsed = _elapsed(t_total)
        logger.info(
            "[MinerU] ═══ 云解析完成: %s → %d chars Markdown  总耗时=%s ═══",
            filename, len(markdown), total_elapsed,
        )
        return markdown

    # ═══════════════════════════════════════════════════════
    #  Step 1: 请求签名上传 URL
    # ═══════════════════════════════════════════════════════

    def _step1_request_upload_url(
        self, filename: str, model: str, is_ocr: bool,
        enable_formula: bool, enable_table: bool, language: str,
    ) -> Optional[str]:
        url = f"{BASE_URL}/file-urls/batch"
        payload = {
            "enable_formula": enable_formula,
            "enable_table": enable_table,
            "is_ocr": is_ocr,
            "language": language,
            "model_version": model,
            "files": [{"name": filename}],
        }

        logger.info(
            "[MinerU:1] POST %s  model=%s  filename=%s",
            url, model, filename,
        )
        logger.debug("[MinerU:1] payload: %s", payload)

        try:
            t0 = time.time()
            resp = httpx.post(url, headers=self.headers, json=payload, timeout=30)
            latency = _elapsed(t0)
            data = resp.json()

            logger.info(
                "[MinerU:1] 响应: HTTP %d  耗时=%s  字节=%d",
                resp.status_code, latency, len(resp.content),
            )

            if data.get("code") != 0:
                logger.error(
                    "[MinerU:1] 业务错误: code=%s  msg=%s",
                    data.get("code"), data.get("msg", data),
                )
                return None

            batch_id = data["data"]["batch_id"]
            self._signed_url = data["data"]["file_urls"][0]
            logger.info(
                "[MinerU:1] batch_id=%s  signed_url_prefix=%s...",
                batch_id, self._signed_url[:60],
            )
            return batch_id

        except httpx.TimeoutException as e:
            logger.error("[MinerU:1] 请求超时: %s", e)
            return None
        except httpx.ConnectError as e:
            logger.error("[MinerU:1] 连接失败: %s (可能是网络问题)", e)
            return None
        except Exception as e:
            logger.error("[MinerU:1] 异常: %s  type=%s", e, type(e).__name__)
            return None

    # ═══════════════════════════════════════════════════════
    #  Step 2: PUT 上传文件
    # ═══════════════════════════════════════════════════════

    def _step2_upload_file(self, file_bytes: bytes, filename: str) -> bool:
        size_mb = len(file_bytes) / 1024 / 1024
        signed_prefix = self._signed_url[:80]

        logger.info(
            "[MinerU:2] PUT 上传文件  name=%s  size=%s  url=%s...",
            filename, _sz(len(file_bytes)), signed_prefix,
        )
        logger.debug(
            "[MinerU:2] signed_url_full=%s", self._signed_url,
        )

        try:
            t0 = time.time()
            resp = httpx.put(
                self._signed_url,
                content=file_bytes,
                timeout=max(60, 5 * size_mb),  # 每 MB 给 5s
            )
            latency = _elapsed(t0)
            speed = (len(file_bytes) / 1024) / max(float(latency[:-1]), 0.01) if latency.endswith("s") else 0

            logger.info(
                "[MinerU:2] 响应: HTTP %d  耗时=%s  上传速度=%.1fKB/s",
                resp.status_code, latency, speed,
            )

            if resp.status_code in (200, 201):
                logger.info("[MinerU:2] 上传成功")
                return True

            logger.error(
                "[MinerU:2] 上传失败: HTTP %d  body=%s",
                resp.status_code, resp.text[:300],
            )
            return False

        except httpx.TimeoutException as e:
            logger.error(
                "[MinerU:2] 上传超时: %s (文件=%s, 超时阈值=%.0fs)",
                e, _sz(len(file_bytes)), max(60, 5 * size_mb),
            )
            return False
        except Exception as e:
            logger.error("[MinerU:2] 上传异常: %s  type=%s", e, type(e).__name__)
            return False

    # ═══════════════════════════════════════════════════════
    #  Step 3: 轮询解析结果
    # ═══════════════════════════════════════════════════════

    def _step3_poll_result(self, batch_id: str) -> Optional[bytes]:
        url = f"{BASE_URL}/extract-results/batch/{batch_id}"
        waited = 0
        poll_count = 0

        logger.info("[MinerU:3] 轮询地址: %s", url)

        while waited < POLL_TIMEOUT:
            poll_count += 1
            time.sleep(POLL_INTERVAL)
            waited += POLL_INTERVAL

            try:
                t0 = time.time()
                resp = httpx.get(url, headers=self.headers, timeout=30)
                req_latency = _elapsed(t0)
                data = resp.json()

                if data.get("code") != 0:
                    logger.warning(
                        "[MinerU:3] 第%d次轮询异常: code=%s  msg=%s  耗时=%s",
                        poll_count, data.get("code"), data.get("msg"), req_latency,
                    )
                    continue

                results = data.get("data", {}).get("extract_result", [])
                if not results:
                    logger.debug("[MinerU:3] 第%d次轮询: extract_result 为空", poll_count)
                    continue

                state = results[0].get("state", "")

                if state == "done":
                    zip_url = results[0].get("full_zip_url", "")
                    if not zip_url:
                        logger.error("[MinerU:3] state=done 但 full_zip_url 为空")
                        return None

                    logger.info(
                        "[MinerU:3] 解析完成! 轮询次数=%d  总轮询耗时=%ds  开始下载 ...",
                        poll_count, waited,
                    )
                    logger.debug("[MinerU:3] zip_url=%s", zip_url)

                    dl_t0 = time.time()
                    zip_resp = httpx.get(zip_url, timeout=120)
                    dl_latency = _elapsed(dl_t0)
                    logger.info(
                        "[MinerU:3] 下载 zip 完成: HTTP %d  size=%s  耗时=%s",
                        zip_resp.status_code, _sz(len(zip_resp.content)), dl_latency,
                    )
                    return zip_resp.content

                elif state == "failed":
                    err_msg = results[0].get("err_msg", "")
                    file_name = results[0].get("file_name", "")
                    logger.error(
                        "[MinerU:3] 解析失败! file=%s  err=%s  轮询次数=%d  耗时=%ds",
                        file_name, err_msg, poll_count, waited,
                    )
                    return None

                else:
                    logger.info(
                        "[MinerU:3] 第%d次轮询: state=%s  (%ds/%ds)  耗时=%s",
                        poll_count, state, waited, POLL_TIMEOUT, req_latency,
                    )

            except httpx.TimeoutException as e:
                logger.warning("[MinerU:3] 第%d次轮询超时: %s", poll_count, e)
            except httpx.ConnectError as e:
                logger.warning("[MinerU:3] 第%d次轮询连接失败: %s", poll_count, e)
            except Exception as e:
                logger.warning("[MinerU:3] 第%d次轮询异常: %s", poll_count, e)

        logger.error(
            "[MinerU:3] 轮询超时! 轮询次数=%d  总等待=%ds  超时阈值=%ds",
            poll_count, waited, POLL_TIMEOUT,
        )
        return None

    # ═══════════════════════════════════════════════════════
    #  Step 4: 提取 Markdown
    # ═══════════════════════════════════════════════════════

    _last_zip_count = 0

    def _step4_extract_markdown(self, zip_bytes: bytes) -> str:
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                names = zf.namelist()
                self._last_zip_count = len(names)

                logger.info(
                    "[MinerU:4] zip 包: %d 个文件  总大小=%s",
                    len(names), _sz(len(zip_bytes)),
                )
                logger.debug("[MinerU:4] 文件列表: %s", names)

                for name in names:
                    info = zf.getinfo(name)
                    logger.debug(
                        "[MinerU:4]   %-40s  %s  compressed=%s",
                        name, _sz(info.file_size), _sz(info.compress_size),
                    )

                md_files = [n for n in names if n.endswith(".md")]
                if not md_files:
                    logger.warning("[MinerU:4] zip 中未找到 .md 文件! 全部文件: %s", names)
                    return ""

                md_name = md_files[0]
                content = zf.read(md_name).decode("utf-8", errors="replace")
                line_count = content.count("\n") + 1

                logger.info(
                    "[MinerU:4] 提取: %s  chars=%d  lines=%d",
                    md_name, len(content), line_count,
                )
                return content

        except zipfile.BadZipFile as e:
            logger.error("[MinerU:4] zip 文件损坏: %s", e)
            return ""
        except Exception as e:
            logger.error("[MinerU:4] 解压异常: %s  type=%s", e, type(e).__name__)
            return ""
